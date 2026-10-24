/**
 * Tiptap extension that draws Layer A findings as inline decorations.
 *
 * Findings carry character offsets into the plain text. `docToText` builds that
 * plain text from the ProseMirror document together with a map from each
 * character to its document position, so offsets can be turned back into ranges.
 * Block boundaries become "\n" (mapped to -1), the same text the backend checks.
 */
import { Extension, type Editor } from "@tiptap/core";
import type { Node as PMNode } from "@tiptap/pm/model";
import { Plugin, PluginKey } from "@tiptap/pm/state";
import { Decoration, DecorationSet } from "@tiptap/pm/view";
import type { Finding, ImageRef, Span } from "@/lib/types";

export const layerAKey = new PluginKey<DecorationSet>("layerAHighlights");

export function docToText(doc: PMNode): { text: string; posMap: number[] } {
  let text = "";
  const posMap: number[] = [];
  let firstBlock = true;
  doc.descendants((node, pos) => {
    if (node.isTextblock) {
      if (!firstBlock) {
        text += "\n";
        posMap.push(-1);
      }
      firstBlock = false;
    }
    if (node.isText && node.text) {
      for (let i = 0; i < node.text.length; i++) {
        text += node.text[i];
        posMap.push(pos + i);
      }
    } else if (node.type.name === "hardBreak") {
      text += "\n";
      posMap.push(-1);
    }
    return true;
  });
  return { text, posMap };
}

export function collectImages(doc: PMNode): ImageRef[] {
  const out: ImageRef[] = [];
  doc.descendants((node) => {
    if (node.type.name === "image") {
      const alt = node.attrs.alt as string | null | undefined;
      out.push({ src: String(node.attrs.src ?? ""), alt: alt === undefined || alt === null ? null : alt });
    }
    return true;
  });
  return out;
}

export function spanToRange(span: Span, posMap: number[]): { from: number; to: number } | null {
  let from = -1;
  let to = -1;
  for (let i = span.start; i < span.end && i < posMap.length; i++) {
    const p = posMap[i];
    if (p < 0) continue;
    if (from < 0) from = p;
    to = p + 1;
  }
  return from < 0 ? null : { from, to };
}

export const LayerAHighlights = Extension.create({
  name: "layerAHighlights",
  addProseMirrorPlugins() {
    return [
      new Plugin<DecorationSet>({
        key: layerAKey,
        state: {
          init: () => DecorationSet.empty,
          apply(tr, old) {
            const next = tr.getMeta(layerAKey) as DecorationSet | undefined;
            return next ?? old.map(tr.mapping, tr.doc);
          },
        },
        props: {
          decorations(state) {
            return layerAKey.getState(state);
          },
        },
      }),
    ];
  },
});

export function applyFindings(editor: Editor, findings: Finding[], posMap: number[], activeId?: string | null) {
  const decos: Decoration[] = [];
  for (const f of findings) {
    if (!f.span) continue;
    const r = spanToRange(f.span, posMap);
    if (!r || r.to <= r.from) continue;
    decos.push(
      Decoration.inline(r.from, r.to, {
        class: `la-${f.severity}${f.id === activeId ? " la-active" : ""}`,
        "data-finding-id": f.id,
        title: f.message,
      }),
    );
  }
  const set = DecorationSet.create(editor.state.doc, decos);
  editor.view.dispatch(editor.state.tr.setMeta(layerAKey, set).setMeta("addToHistory", false));
}
