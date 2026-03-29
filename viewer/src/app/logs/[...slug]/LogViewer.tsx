"use client";

import { useState, useCallback } from "react";
import MarkdownRenderer from "@/components/MarkdownRenderer";

function parseFrontmatterSimple(raw: string): { content: string; frontmatter: Record<string, string> } {
  const match = raw.match(/^---\s*\n([\s\S]*?)\n---\s*\n([\s\S]*)$/);
  if (!match) return { content: raw, frontmatter: {} };

  const fm: Record<string, string> = {};
  for (const line of match[1].split("\n")) {
    const idx = line.indexOf(":");
    if (idx > 0) {
      fm[line.slice(0, idx).trim()] = line.slice(idx + 1).trim().replace(/^["']|["']$/g, "");
    }
  }
  return { content: match[2], frontmatter: fm };
}

export default function LogViewer({
  filePath,
  initialRaw,
  initialContent,
  frontmatter: initialFrontmatter,
}: {
  filePath: string;
  initialRaw: string;
  initialContent: string;
  frontmatter: Record<string, string>;
}) {
  const [isEditing, setIsEditing] = useState(false);
  const [rawContent, setRawContent] = useState(initialRaw);
  const [displayContent, setDisplayContent] = useState(initialContent);
  const [frontmatter, setFrontmatter] = useState(initialFrontmatter);
  const [editContent, setEditContent] = useState(initialRaw);
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<"idle" | "saved" | "error">("idle");

  const pathParts = filePath.replace(/\.md$/, "").split("/");

  const handleEdit = useCallback(() => {
    setEditContent(rawContent);
    setIsEditing(true);
    setSaveStatus("idle");
  }, [rawContent]);

  const handleCancel = useCallback(() => {
    setIsEditing(false);
    setEditContent(rawContent);
    setSaveStatus("idle");
  }, [rawContent]);

  const handleSave = useCallback(async () => {
    setSaving(true);
    setSaveStatus("idle");
    try {
      const res = await fetch("/api/file", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: filePath, content: editContent }),
      });

      if (!res.ok) throw new Error("Save failed");

      setRawContent(editContent);
      const parsed = parseFrontmatterSimple(editContent);
      setDisplayContent(parsed.content);
      setFrontmatter(parsed.frontmatter);
      setIsEditing(false);
      setSaveStatus("saved");
      setTimeout(() => setSaveStatus("idle"), 2000);
    } catch {
      setSaveStatus("error");
    } finally {
      setSaving(false);
    }
  }, [filePath, editContent]);

  return (
    <div>
      {/* Breadcrumb + Actions */}
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-sm text-neutral-400">
          {pathParts.map((part, i) => (
            <span key={i} className="flex items-center gap-1.5">
              {i > 0 && <span>/</span>}
              <span className={i === pathParts.length - 1 ? "text-neutral-600" : ""}>
                {part}
              </span>
            </span>
          ))}
        </div>

        <div className="flex items-center gap-2">
          {saveStatus === "saved" && (
            <span className="text-xs text-green-600">저장 완료</span>
          )}
          {saveStatus === "error" && (
            <span className="text-xs text-red-600">저장 실패</span>
          )}

          {isEditing ? (
            <>
              <button
                onClick={handleCancel}
                className="rounded-md border border-neutral-200 px-3 py-1.5 text-xs font-medium text-neutral-600 hover:bg-neutral-50 transition-colors"
              >
                취소
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                {saving ? "저장 중..." : "저장"}
              </button>
            </>
          ) : (
            <button
              onClick={handleEdit}
              className="rounded-md border border-neutral-200 px-3 py-1.5 text-xs font-medium text-neutral-600 hover:bg-neutral-50 transition-colors"
            >
              편집
            </button>
          )}
        </div>
      </div>

      {/* Meta badges */}
      <div className="mb-8 flex flex-wrap items-center gap-2">
        {frontmatter.date && (
          <span className="rounded-md bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700">
            {frontmatter.date}
          </span>
        )}
        {frontmatter.agent && (
          <span className="rounded-md bg-neutral-100 px-2 py-0.5 text-xs font-medium text-neutral-600">
            {frontmatter.agent}
          </span>
        )}
        {frontmatter.type && (
          <span className="rounded-md bg-neutral-100 px-2 py-0.5 text-xs font-medium text-neutral-600">
            {frontmatter.type}
          </span>
        )}
        {frontmatter.period && (
          <span className="rounded-md bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700">
            {frontmatter.period}
          </span>
        )}
      </div>

      {/* Content: View or Edit */}
      {isEditing ? (
        <textarea
          value={editContent}
          onChange={(e) => setEditContent(e.target.value)}
          className="w-full min-h-[600px] rounded-lg border border-neutral-200 bg-neutral-50 p-4 font-mono text-[13px] leading-relaxed text-neutral-800 focus:border-blue-300 focus:outline-none focus:ring-1 focus:ring-blue-300 resize-y"
          spellCheck={false}
        />
      ) : (
        <MarkdownRenderer content={displayContent} />
      )}
    </div>
  );
}
