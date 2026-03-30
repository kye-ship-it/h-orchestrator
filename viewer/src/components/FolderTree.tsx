"use client";

import { useState } from "react";
import Link from "next/link";
import type { FileNode } from "@/lib/types";

interface FolderTreeProps {
  nodes: FileNode[];
  activePath?: string;
  depth?: number;
}

function TreeItem({
  node,
  activePath,
  depth = 0,
}: {
  node: FileNode;
  activePath?: string;
  depth?: number;
}) {
  const isActive = activePath === node.path;
  const isAncestor = activePath ? activePath.startsWith(node.path) : false;
  const [open, setOpen] = useState(isAncestor || depth === 0);

  const indent = depth * 16 + 8;
  const displayName = node.type === "file" ? node.name.replace(/\.md$/, "") : node.name;

  if (node.type === "folder") {
    return (
      <div>
        <button
          onClick={() => setOpen(!open)}
          className="flex w-full items-center gap-1 rounded-md py-[5px] text-[13px] text-neutral-500 hover:bg-neutral-200/60 hover:text-neutral-800 transition-colors"
          style={{ paddingLeft: `${indent}px`, paddingRight: "8px" }}
        >
          <svg
            width="12"
            height="12"
            viewBox="0 0 16 16"
            fill="none"
            className={`shrink-0 transition-transform duration-100 ${open ? "rotate-90" : ""}`}
          >
            <path d="M6 4l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span className="truncate">{displayName}</span>
        </button>
        {open && node.children && (
          <div>
            {node.children.map((child) => (
              <TreeItem key={child.path} node={child} activePath={activePath} depth={depth + 1} />
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <Link
      href={`/logs/${node.path.split('/').map(encodeURIComponent).join('/')}`}
      className={`flex items-center gap-1.5 rounded-md py-[5px] text-[13px] transition-colors ${
        isActive
          ? "bg-blue-50 text-blue-700 font-medium"
          : "text-neutral-600 hover:bg-neutral-200/60 hover:text-neutral-800"
      }`}
      style={{ paddingLeft: `${indent + 14}px`, paddingRight: "8px" }}
    >
      <svg width="12" height="12" viewBox="0 0 16 16" fill="none" className="shrink-0">
        <path
          d="M4 2h5l4 4v8a1 1 0 01-1 1H4a1 1 0 01-1-1V3a1 1 0 011-1z"
          stroke="currentColor"
          strokeWidth="1.3"
          fill={isActive ? "rgba(59,130,246,0.08)" : "none"}
        />
        <path d="M9 2v4h4" stroke="currentColor" strokeWidth="1.3" />
      </svg>
      <span className="truncate">{displayName}</span>
    </Link>
  );
}

export function FolderTree({ nodes, activePath, depth = 0 }: FolderTreeProps) {
  return (
    <div>
      {nodes.map((node) => (
        <TreeItem key={node.path} node={node} activePath={activePath} depth={depth} />
      ))}
    </div>
  );
}
