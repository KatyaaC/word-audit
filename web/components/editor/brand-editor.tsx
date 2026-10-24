"use client";

import { useEffect, useImperativeHandle, useRef, forwardRef } from "react";
import { EditorContent, useEditor, type Editor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Image from "@tiptap/extension-image";
import { Bold, Heading2, ImagePlus, Italic, List, ListOrdered, Redo2, Undo2 } from "lucide-react";
import { Button } from "@/components/ui/primitives";
import { runLayerALocal } from "@/lib/layer-a";
import type { ColourPair, Finding, ImageRef, Span } from "@/lib/types";
import { LayerAHighlights, applyFindings, collectImages, docToText, spanToRange } from "./layer-a-extension";

export interface EditorSnapshot {
  text: string;
  html: string;
  images: ImageRef[];
}

export interface EditorHandle {
  focusSpan: (span: Span) => void;
  replaceSpan: (span: Span, text: string) => void;
  appendText: (text: string) => void;
}

interface Props {
  initialHtml: string;
  colourPairs: ColourPair[];
  activeFindingId: string | null;
  onChange: (snap: EditorSnapshot, findings: Finding[]) => void;
  onFindingClick: (id: string) => void;
}

/** Rich-text editor with real-time Layer A feedback. */
export const BrandEditor = forwardRef<EditorHandle, Props>(function BrandEditor(
  { initialHtml, colourPairs, activeFindingId, onChange, onFindingClick },
  ref,
) {
  const posMapRef = useRef<number[]>([]);
  const findingsRef = useRef<Finding[]>([]);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const editorRef = useRef<Editor | null>(null);
  // Refs keep the latest props visible inside Tiptap callbacks without re-creating the editor
  const latest = useRef({ colourPairs, activeFindingId, onChange, onFindingClick });
  latest.current = { colourPairs, activeFindingId, onChange, onFindingClick };

  const editor = useEditor({
    immediatelyRender: false,
    extensions: [StarterKit.configure({ heading: { levels: [2, 3] } }), Image.configure({ allowBase64: true }), LayerAHighlights],
    content: initialHtml,
    editorProps: {
      attributes: { class: "ProseMirror px-1", "aria-label": "Content editor" },
      handleClick(_view, _pos, event) {
        const el = (event.target as HTMLElement).closest("[data-finding-id]");
        if (el) latest.current.onFindingClick(el.getAttribute("data-finding-id")!);
        return false;
      },
    },
    onCreate: ({ editor: e }) => {
      editorRef.current = e;
      schedule(0);
    },
    onUpdate: ({ editor: e }) => {
      editorRef.current = e;
      schedule(200);
    },
  });
  editorRef.current = editor ?? editorRef.current;

  function runChecks() {
    const editor = editorRef.current;
    if (!editor || editor.isDestroyed) return;
    const { text, posMap } = docToText(editor.state.doc);
    const images = collectImages(editor.state.doc);
    const html = editor.getHTML();
    posMapRef.current = posMap;
    const findings = runLayerALocal({ text, html, images, colour_pairs: latest.current.colourPairs });
    findingsRef.current = findings;
    applyFindings(editor, findings, posMap, latest.current.activeFindingId);
    latest.current.onChange({ text, html, images }, findings);
  }

  function schedule(ms: number) {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(runChecks, ms);
  }

  // Re-run when colour pairs change; redraw when the active finding changes
  useEffect(() => schedule(100), [colourPairs, editor]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (editor && !editor.isDestroyed) applyFindings(editor, findingsRef.current, posMapRef.current, activeFindingId);
  }, [activeFindingId, editor]);
  useEffect(() => () => void (timer.current && clearTimeout(timer.current)), []);

  useImperativeHandle(
    ref,
    () => ({
      focusSpan(span) {
        const r = editor && spanToRange(span, posMapRef.current);
        if (editor && r) editor.chain().focus().setTextSelection(r).scrollIntoView().run();
      },
      replaceSpan(span, text) {
        const r = editor && spanToRange(span, posMapRef.current);
        if (editor && r) editor.chain().focus().insertContentAt(r, text).run();
      },
      appendText(text) {
        if (editor) editor.chain().focus("end").insertContent(` ${text}`).run();
      },
    }),
    [editor],
  );

  function insertImage() {
    if (!editor) return;
    const src = window.prompt("Image URL", "https://placehold.co/600x300/png?text=Campaign+image");
    if (!src) return;
    const alt = window.prompt("Alt text (leave empty to test the missing alt-text check)", "");
    editor
      .chain()
      .focus()
      .setImage(alt ? { src, alt } : { src })
      .run();
  }

  const btn = (label: string, onClick: () => void, Icon: typeof Bold, active = false) => (
    <Button type="button" variant={active ? "secondary" : "ghost"} size="icon" aria-label={label} title={label} onClick={onClick}>
      <Icon className="h-4 w-4" />
    </Button>
  );

  return (
    <div className="rounded-lg border border-stone-300 bg-white">
      <div className="flex flex-wrap items-center gap-0.5 border-b border-stone-200 p-1.5">
        {editor && (
          <>
            {btn("Bold", () => editor.chain().focus().toggleBold().run(), Bold, editor.isActive("bold"))}
            {btn("Italic", () => editor.chain().focus().toggleItalic().run(), Italic, editor.isActive("italic"))}
            {btn("Heading", () => editor.chain().focus().toggleHeading({ level: 2 }).run(), Heading2, editor.isActive("heading"))}
            {btn("Bullet list", () => editor.chain().focus().toggleBulletList().run(), List, editor.isActive("bulletList"))}
            {btn("Numbered list", () => editor.chain().focus().toggleOrderedList().run(), ListOrdered, editor.isActive("orderedList"))}
            {btn("Insert image", insertImage, ImagePlus)}
            <span className="mx-1 h-5 w-px bg-stone-200" />
            {btn("Undo", () => editor.chain().focus().undo().run(), Undo2)}
            {btn("Redo", () => editor.chain().focus().redo().run(), Redo2)}
          </>
        )}
      </div>
      <div className="px-4 py-2">
        <EditorContent editor={editor} />
      </div>
    </div>
  );
});
