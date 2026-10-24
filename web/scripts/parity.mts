// Checks that the in-editor TypeScript Layer A gives the same rule IDs as the Python service
// on every synthetic item. Run: npm run parity
import { readFileSync } from "node:fs";
import { runLayerALocal } from "../lib/layer-a";

const items = JSON.parse(readFileSync(new URL("../../services/layer_a/data/synthetic_rule_tone_a11y.json", import.meta.url), "utf8")).items;
const imgRe = /<img\b([^>]*)>/gi;
const attr = (s: string, n: string) => { const m = new RegExp(`${n}\\s*=\\s*"([^"]*)"`, "i").exec(s); return m ? m[1] : null; };
let bad = 0;
for (const it of items) {
  const images = [...(it.html ?? "").matchAll(imgRe)].map((m) => ({ src: attr(m[1], "src") ?? "", alt: attr(m[1], "alt") }));
  const got = runLayerALocal({ text: it.text, html: it.html, colour_pairs: it.colour_pairs ?? [], images }).map((f) => f.rule_id).sort();
  const exp = [...it.expected].sort();
  const ok = JSON.stringify(got) === JSON.stringify(exp);
  if (!ok) bad++;
  console.log(`${it.id.padEnd(4)} ${ok ? "ok  " : "MISS"} expected=${JSON.stringify(exp)} got=${JSON.stringify(got)}`);
}
console.log(bad ? `\n${bad} mismatches` : `\nAll ${items.length} items match the expected labels.`);
process.exit(bad ? 1 : 0);
