/**
 * In-editor mirror of Layer A (services/layer_a).
 *
 * The editor runs these checks on every keystroke so highlights appear instantly
 * without a network call. The Python service stays the source of truth: when the
 * creator clicks "Run full review", the backend re-runs Layer A and its result is
 * what gets stored. Both use the same rule pack JSON and the same regex rules,
 * so the rule IDs and spans agree.
 */
import defaultPack from "./default-rule-pack.json";
import type { Finding, LayerACheckRequest, RulePack, Severity, Span, TermRule } from "./types";

export const DEFAULT_RULE_PACK = defaultPack as unknown as RulePack;

const BL = "(?<![\\w-])";
const BR = "(?![\\w-])";
const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

export function phrasePattern(term: string, inflect: boolean): string {
  const words = term.trim().split(/\s+/);
  const parts = words.map(esc);
  const last = words[words.length - 1];
  if (inflect && /[a-z]$/i.test(last)) {
    parts[parts.length - 1] = last.toLowerCase().endsWith("e")
      ? esc(last.slice(0, -1)) + "(?:e|es|ed|ing|eing)"
      : esc(last) + "(?:s|es|ed|ing)?";
  }
  return BL + parts.join("\\s+") + BR;
}

function spans(text: string, term: string, inflect: boolean, caseSensitive: boolean): Span[] {
  const re = new RegExp(phrasePattern(term, inflect), caseSensitive ? "g" : "gi");
  const out: Span[] = [];
  for (const m of text.matchAll(re)) {
    const start = m.index ?? 0;
    out.push({ start, end: start + m[0].length });
  }
  return out;
}

function dedupe(list: Span[]): Span[] {
  const sorted = [...list].sort((a, b) => a.start - b.start || b.end - b.start - (a.end - a.start));
  const out: Span[] = [];
  for (const s of sorted) {
    if (out.length && s.start < out[out.length - 1].end) continue;
    out.push(s);
  }
  return out;
}

function findRule(text: string, rule: TermRule): Span[] {
  const inflect = rule.match === "lemma";
  return dedupe(rule.terms.flatMap((t) => spans(text, t, inflect, !!rule.case_sensitive)));
}

const triggersIn = (text: string, terms: string[]) => terms.filter((t) => spans(text, t, false, false).length > 0);

function fid(...parts: (string | number)[]): string {
  let h = 0x811c9dc5;
  const s = parts.join("|");
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return "A-" + h.toString(16).padStart(8, "0");
}

// ---------- Contrast (WCAG 2.x) ----------

export function parseColour(value: string): [number, number, number] | null {
  const v = value.trim();
  const hex = v.match(/^#?([0-9a-f]{3}|[0-9a-f]{6})$/i);
  if (hex) {
    let h = hex[1];
    if (h.length === 3) h = h.split("").map((c) => c + c).join("");
    return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
  }
  const rgb = v.match(/^rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})/i);
  if (rgb) return [rgb[1], rgb[2], rgb[3]].map((x) => Math.min(255, Number(x))) as [number, number, number];
  return null;
}

const channel = (c: number) => {
  const s = c / 255;
  return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
};

export function relativeLuminance([r, g, b]: [number, number, number]): number {
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

export function contrastRatio(fg: string, bg: string): number | null {
  const a = parseColour(fg);
  const b = parseColour(bg);
  if (!a || !b) return null;
  const l1 = relativeLuminance(a);
  const l2 = relativeLuminance(b);
  return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
}

// ---------- Alt text ----------

const FILENAME_LIKE = /(\.(jpe?g|png|gif|webp|svg|bmp)$)|^(img|dsc|image|photo|pic|screenshot)[\s_-]?\d+/i;
const GENERIC_ALT = new Set(["image", "picture", "photo", "img", "graphic", "logo", "banner", "icon", "alt"]);

// ---------- Engine ----------

const RANK: Record<Severity, number> = { high: 0, medium: 1, low: 2 };

export function runLayerALocal(req: LayerACheckRequest, pack: RulePack = DEFAULT_RULE_PACK): Finding[] {
  const { text } = req;
  const base = {
    layer: "A" as const,
    source: "fixed_check" as const,
    status: "rule_violation" as const,
    rule_version: pack.version,
  };
  const out: Finding[] = [];

  for (const rule of pack.terms) {
    if (rule.kind === "banned") {
      for (const sp of findRule(text, rule)) {
        const matched = text.slice(sp.start, sp.end);
        out.push({
          ...base,
          id: fid(rule.id, sp.start, sp.end),
          kind: "banned_term",
          rule_id: rule.id,
          severity: rule.severity,
          message: `Try to avoid "${matched}" here.`,
          explanation: `${rule.reason} (From: ${rule.source_ref}.)`,
          span: sp,
          matched_text: matched,
          fix_type: rule.replacement ? "replace" : "advice",
          suggestion: rule.replacement,
        });
      }
    } else {
      const when = rule.when_any ?? [];
      const trig = when.length ? triggersIn(text, when) : [];
      const applies = when.length === 0 || trig.length > 0;
      if (applies && findRule(text, rule).length === 0) {
        out.push({
          ...base,
          id: fid(rule.id, "missing"),
          kind: "required_term_missing",
          rule_id: rule.id,
          severity: rule.severity,
          message: `This needs to include "${rule.terms[0]}".`,
          explanation: `${rule.reason}${trig.length ? ` You mentioned: ${trig.join(", ")}.` : ""} (From: ${rule.source_ref}.)`,
          fix_type: "insert",
          suggestion: rule.terms[0] + ".",
        });
      }
    }
  }

  // Tone: exclamation marks
  const t = pack.tone;
  const bangs = [...text].reduce<number[]>((acc, c, i) => (c === "!" ? (acc.push(i), acc) : acc), []);
  if (bangs.length > t.max_exclamations) {
    const start = bangs[t.max_exclamations];
    let end = start;
    while (end < text.length && text[end] === "!") end++;
    out.push({
      ...base,
      id: fid(t.exclamation_rule_id, start),
      kind: "tone_exclamation",
      rule_id: t.exclamation_rule_id,
      severity: t.severity,
      message: `That's ${bangs.length} exclamation marks. We keep it to ${t.max_exclamations}.`,
      explanation: "Our voice is calm and confident. A run of exclamation marks can come across as pushy.",
      span: { start, end },
      matched_text: text.slice(start, end),
      fix_type: "replace",
      suggestion: "",
    });
  }

  // Tone: shouting
  const allowed = new Set(t.allowed_acronyms.map((a) => a.toUpperCase()));
  for (const m of text.matchAll(new RegExp(`\\b[A-Z]{${t.shouting_min_length},}\\b`, "g"))) {
    if (allowed.has(m[0])) continue;
    const start = m.index ?? 0;
    out.push({
      ...base,
      id: fid(t.shouting_rule_id, start),
      kind: "tone_shouting",
      rule_id: t.shouting_rule_id,
      severity: t.severity,
      message: `"${m[0]}" reads like shouting.`,
      explanation: "Try normal sentence case instead. Approved acronyms like SEBI are fine.",
      span: { start, end: start + m[0].length },
      matched_text: m[0],
      fix_type: "replace",
      suggestion: start === 0 ? m[0][0] + m[0].slice(1).toLowerCase() : m[0].toLowerCase(),
    });
  }

  // Contrast
  const c = pack.contrast;
  for (const pair of req.colour_pairs) {
    const ratio = contrastRatio(pair.foreground, pair.background);
    if (ratio === null) continue;
    const required = pair.large_text ? c.large_text_min_ratio : c.min_ratio;
    if (ratio < required) {
      out.push({
        ...base,
        id: fid(c.rule_id, pair.element, pair.foreground, pair.background),
        kind: "low_contrast",
        rule_id: c.rule_id,
        severity: c.severity,
        message: `${pair.element} may be hard to read: the contrast is ${ratio.toFixed(2)}:1 and it needs at least ${required}:1.`,
        explanation:
          "Low-contrast text is hard for many people to read, especially on a phone outdoors. WCAG AA asks for 4.5:1 for normal text and 3:1 for large text.",
        target: pair.element,
        fix_type: "advice",
        suggestion: "Try a darker text colour or a lighter background.",
      });
    }
  }

  // Alt text
  const a = pack.alt_text;
  req.images.forEach((img, idx) => {
    if (img.decorative) return;
    const label = img.src ? img.src.slice(0, 60) : `image #${idx + 1}`;
    if (img.alt === null || img.alt === undefined) {
      out.push({
        ...base,
        id: fid(a.missing_rule_id, img.src, idx),
        kind: "missing_alt_text",
        rule_id: a.missing_rule_id,
        severity: a.missing_severity,
        message: `This image (${label}) has no description.`,
        explanation:
          "People using screen readers won't know what it shows. Add a short description, or mark it as decorative.",
        target: img.src,
        fix_type: "advice",
        suggestion: "Describe what the image shows in a few words.",
      });
      return;
    }
    const alt = img.alt.trim();
    const empty = alt === "";
    if (empty || FILENAME_LIKE.test(alt) || GENERIC_ALT.has(alt.toLowerCase())) {
      out.push({
        ...base,
        id: fid(a.weak_rule_id, img.src, idx),
        kind: "weak_alt_text",
        rule_id: a.weak_rule_id,
        severity: empty ? "low" : a.weak_severity,
        message: `This image (${label}) needs a better description.`,
        explanation: empty
          ? "The description is empty, so screen readers will skip this image. That's fine only if it's purely decorative."
          : `The description "${img.alt}" looks like a file name or a placeholder.`,
        target: img.src,
        fix_type: "advice",
        suggestion: "Say what the image shows and why it's there, in a short phrase.",
      });
    }
  });

  return out.sort(
    (x, y) =>
      RANK[x.severity] - RANK[y.severity] ||
      (x.span?.start ?? 1e9) - (y.span?.start ?? 1e9) ||
      String(x.rule_id).localeCompare(String(y.rule_id)),
  );
}
