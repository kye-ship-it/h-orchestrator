"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { FolderTree } from "@/components/FolderTree";
import type { FileNode } from "@/lib/types";

export function Sidebar() {
  const [tree, setTree] = useState<FileNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [collapsed, setCollapsed] = useState(false);
  const router = useRouter();
  const pathname = usePathname();

  const activePath = pathname.startsWith("/logs/")
    ? pathname.replace("/logs/", "").split('/').map(decodeURIComponent).join('/')
    : undefined;

  useEffect(() => {
    fetch("/api/files")
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => setTree(Array.isArray(data) ? data : data.tree ?? []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleSearch = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      const q = searchQuery.trim();
      if (q) router.push(`/search?q=${encodeURIComponent(q)}`);
    },
    [searchQuery, router]
  );

  if (collapsed) {
    return (
      <aside className="flex w-10 shrink-0 flex-col items-center border-r border-neutral-200 bg-neutral-50 py-3">
        <button
          onClick={() => setCollapsed(false)}
          className="rounded p-1 text-neutral-400 hover:bg-neutral-200 hover:text-neutral-600"
          aria-label="Expand sidebar"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M6 3l5 5-5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </aside>
    );
  }

  return (
    <aside className="flex w-[260px] shrink-0 flex-col border-r border-neutral-200 bg-neutral-50">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3">
        <Link href="/" className="flex items-center gap-2 text-sm font-semibold text-neutral-700">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <rect x="1" y="1" width="14" height="14" rx="3" stroke="currentColor" strokeWidth="1.5" />
            <path d="M5 5h6M5 8h6M5 11h4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
          </svg>
          H-Agent Orchestrator
        </Link>
        <button
          onClick={() => setCollapsed(true)}
          className="rounded p-1 text-neutral-400 hover:bg-neutral-200 hover:text-neutral-600"
          aria-label="Collapse sidebar"
        >
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
            <path d="M10 3L5 8l5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>

      {/* Search */}
      <div className="px-3 pb-2">
        <form onSubmit={handleSearch}>
          <div className="flex items-center gap-2 rounded-md border border-neutral-200 bg-white px-2.5 py-1.5 text-sm text-neutral-500 focus-within:border-neutral-400 focus-within:ring-1 focus-within:ring-neutral-300">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" className="shrink-0">
              <circle cx="7" cy="7" r="5" stroke="currentColor" strokeWidth="1.5" />
              <path d="M11 11l3.5 3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
            <input
              type="text"
              placeholder="Search..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-transparent text-neutral-900 placeholder:text-neutral-400 outline-none"
            />
          </div>
        </form>
      </div>

      {/* Quick Links */}
      <div className="px-3 pb-1">
        <NavLink href="/reports/generate" icon="report" label="New Report" active={pathname === "/reports/generate"} />
      </div>

      <div className="mx-3 border-t border-neutral-200" />

      {/* File Tree */}
      <div className="flex-1 overflow-y-auto px-1 py-2">
        {loading ? (
          <div className="space-y-1 px-3">
            {[75, 60, 80, 55, 70, 45].map((w, i) => (
              <div key={i} className="h-7 animate-pulse rounded bg-neutral-200/60" style={{ width: `${w}%` }} />
            ))}
          </div>
        ) : tree.length === 0 ? (
          <p className="px-3 py-4 text-xs text-neutral-400">No files found</p>
        ) : (
          <FolderTree nodes={tree} activePath={activePath} />
        )}
      </div>
    </aside>
  );
}

function NavLink({ href, icon, label, active }: { href: string; icon: string; label: string; active: boolean }) {
  const icons: Record<string, React.ReactNode> = {
    report: (
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
        <path d="M4 2h5l4 4v8a1 1 0 01-1 1H4a1 1 0 01-1-1V3a1 1 0 011-1z" stroke="currentColor" strokeWidth="1.3" />
        <path d="M9 2v4h4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
        <path d="M6 9h4M6 12h3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      </svg>
    ),
  };

  return (
    <Link
      href={href}
      className={`flex items-center gap-2 rounded-md px-2.5 py-1.5 text-sm transition-colors ${
        active
          ? "bg-neutral-200/80 text-neutral-900 font-medium"
          : "text-neutral-600 hover:bg-neutral-200/50 hover:text-neutral-900"
      }`}
    >
      <span className="text-neutral-400">{icons[icon]}</span>
      {label}
    </Link>
  );
}
