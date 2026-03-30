"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import type { SearchResult } from "@/lib/types";

type SearchMode = "semantic" | "keyword";

function Highlight({ text, query }: { text: string; query: string }) {
  if (!query.trim()) return <>{text}</>;
  const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi");
  const parts = text.split(regex);
  return (
    <>
      {parts.map((part, i) =>
        regex.test(part) ? (
          <mark key={i} className="bg-yellow-100 text-yellow-900 rounded-sm px-0.5">{part}</mark>
        ) : (
          <span key={i}>{part}</span>
        )
      )}
    </>
  );
}

function SearchModeBadge({
  mode,
  onToggle,
}: {
  mode: SearchMode;
  onToggle: () => void;
}) {
  const isSemantic = mode === "semantic";

  return (
    <button
      type="button"
      onClick={onToggle}
      className={`
        inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-medium
        transition-colors cursor-pointer select-none
        ${isSemantic
          ? "bg-indigo-50 text-indigo-600 hover:bg-indigo-100"
          : "bg-neutral-100 text-neutral-500 hover:bg-neutral-200"
        }
      `}
      title={`Currently using ${isSemantic ? "semantic" : "keyword"} search. Click to switch.`}
    >
      {isSemantic ? (
        <svg width="10" height="10" viewBox="0 0 16 16" fill="none" className="shrink-0">
          <circle cx="8" cy="8" r="3" fill="currentColor" />
          <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1" strokeDasharray="3 2" />
        </svg>
      ) : (
        <svg width="10" height="10" viewBox="0 0 16 16" fill="none" className="shrink-0">
          <path d="M2 4h12M2 8h8M2 12h10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      )}
      {isSemantic ? "Semantic" : "Keyword"}
    </button>
  );
}

export default function SearchContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const initialQuery = searchParams.get("q") ?? "";

  const [query, setQuery] = useState(initialQuery);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [searchMode, setSearchMode] = useState<SearchMode>("semantic");
  const [activeMode, setActiveMode] = useState<SearchMode>("semantic");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const performSearch = useCallback(async (q: string, mode: SearchMode = searchMode) => {
    const trimmed = q.trim();
    if (!trimmed) {
      setResults([]);
      setSearched(false);
      return;
    }
    setLoading(true);
    setSearched(true);
    try {
      const res = await fetch(
        `/api/search?q=${encodeURIComponent(trimmed)}&mode=${mode}`
      );
      if (res.ok) {
        const data = await res.json();
        const items = Array.isArray(data) ? data : data.results ?? [];
        setResults(items);
        // Reflect the mode the server actually used
        if (data.mode) {
          setActiveMode(data.mode);
        }
      }
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [searchMode]);

  useEffect(() => {
    if (initialQuery) performSearch(initialQuery);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleChange = (value: string) => {
    setQuery(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      const q = value.trim();
      if (q) router.replace(`/search?q=${encodeURIComponent(q)}`, { scroll: false });
      performSearch(value);
    }, 300);
  };

  const handleToggleMode = () => {
    const next: SearchMode = searchMode === "semantic" ? "keyword" : "semantic";
    setSearchMode(next);
    if (query.trim()) {
      performSearch(query, next);
    }
  };

  return (
    <div>
      <h1 className="text-[26px] font-bold text-neutral-900 mb-1">Search</h1>
      <p className="text-sm text-neutral-500 mb-6">Search across all logs and reports</p>

      <div className="mb-2 flex items-center gap-2 rounded-lg border border-neutral-200 bg-white px-3 py-2.5 shadow-sm focus-within:border-neutral-400 focus-within:ring-2 focus-within:ring-neutral-200 max-w-lg">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="shrink-0 text-neutral-400">
          <circle cx="7" cy="7" r="5" stroke="currentColor" strokeWidth="1.5" />
          <path d="M11 11l3.5 3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
        <input
          type="text"
          placeholder="Type to search..."
          value={query}
          onChange={(e) => handleChange(e.target.value)}
          className="w-full bg-transparent text-[15px] text-neutral-900 placeholder:text-neutral-400 outline-none"
          autoFocus
        />
      </div>

      <div className="mb-8 flex items-center gap-2 max-w-lg">
        <SearchModeBadge mode={activeMode} onToggle={handleToggleMode} />
        {activeMode !== searchMode && searched && (
          <span className="text-[11px] text-neutral-400">
            Index unavailable — using keyword search
          </span>
        )}
      </div>

      {loading && (
        <div className="flex items-center gap-2 text-sm text-neutral-500">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-neutral-300 border-t-neutral-600" />
          Searching...
        </div>
      )}

      {!loading && searched && results.length === 0 && (
        <div className="py-12 text-center text-sm text-neutral-400">
          No results found for &ldquo;{query.trim()}&rdquo;
        </div>
      )}

      {!loading && results.length > 0 && (
        <div>
          <p className="mb-4 text-xs text-neutral-400 uppercase tracking-wider">
            {results.length} result{results.length !== 1 ? "s" : ""}
          </p>
          <div className="space-y-1">
            {results.map((result) => (
              <Link
                key={result.path}
                href={`/logs/${result.path.split('/').map(encodeURIComponent).join('/')}`}
                className="block rounded-lg px-4 py-3 transition-colors hover:bg-neutral-50 border border-transparent hover:border-neutral-200"
              >
                <div className="flex items-center gap-2 mb-1">
                  <svg width="14" height="14" viewBox="0 0 16 16" fill="none" className="text-neutral-400">
                    <path d="M4 2h5l4 4v8a1 1 0 01-1 1H4a1 1 0 01-1-1V3a1 1 0 011-1z" stroke="currentColor" strokeWidth="1.3" />
                    <path d="M9 2v4h4" stroke="currentColor" strokeWidth="1.3" />
                  </svg>
                  <span className="text-sm font-medium text-neutral-800">
                    {result.title || result.path}
                  </span>
                  {result.frontmatter?.date && (
                    <span className="rounded bg-neutral-100 px-1.5 py-0.5 text-[11px] text-neutral-500">
                      {result.frontmatter.date}
                    </span>
                  )}
                  {result.frontmatter?.type && (
                    <span className="rounded bg-neutral-100 px-1.5 py-0.5 text-[11px] text-neutral-500">
                      {result.frontmatter.type}
                    </span>
                  )}
                </div>
                <p className="text-[13px] text-neutral-500 line-clamp-2 pl-[22px]">
                  <Highlight text={result.snippet} query={query.trim()} />
                </p>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
