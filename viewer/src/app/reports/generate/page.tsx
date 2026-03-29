"use client";

import { useState } from "react";
import Link from "next/link";
import MarkdownRenderer from "@/components/MarkdownRenderer";

const REPORT_TYPES = [
  { value: "weekly", label: "주간 리포트" },
  { value: "monthly", label: "월간 리포트" },
  { value: "custom", label: "커스텀 분석" },
];

const METRICS = [
  { value: "funnel", label: "Call Funnel" },
  { value: "qualification", label: "Qualification Depth" },
  { value: "performance", label: "Call Performance" },
  { value: "model", label: "차종별 분석" },
  { value: "dealer", label: "딜러별 분석" },
  { value: "channel", label: "채널별 분석" },
];

export default function GenerateReportPage() {
  const [title, setTitle] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [reportType, setReportType] = useState("weekly");
  const [metrics, setMetrics] = useState<string[]>(["funnel", "qualification", "performance"]);
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<string | null>(null);
  const [savedPath, setSavedPath] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const toggle = (m: string) =>
    setMetrics((prev) => (prev.includes(m) ? prev.filter((x) => x !== m) : [...prev, m]));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setReport(null);
    setSavedPath(null);

    try {
      const res = await fetch("/api/report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, startDate, endDate, reportType, metrics }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error ?? "Failed to generate report");
      }
      const data = await res.json();
      setReport(data.content ?? "");
      setSavedPath(data.path ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setLoading(false);
    }
  };

  const isValid = title.trim() && startDate && endDate && metrics.length > 0;

  return (
    <div>
      <h1 className="text-[26px] font-bold text-neutral-900 mb-1">리포트 생성</h1>
      <p className="text-sm text-neutral-500 mb-8">H-Voice 콜 데이터 기반 분석 리포트를 생성합니다</p>

      <form onSubmit={handleSubmit} className="space-y-6 max-w-lg">
        <div>
          <label className="block text-sm font-medium text-neutral-700 mb-1.5">리포트 제목</label>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="2월 월간 분석 리포트"
            className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-[15px] text-neutral-900 placeholder:text-neutral-400 outline-none focus:border-neutral-400 focus:ring-2 focus:ring-neutral-200"
            required
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-neutral-700 mb-1.5">시작일</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-[15px] text-neutral-900 outline-none focus:border-neutral-400 focus:ring-2 focus:ring-neutral-200"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-neutral-700 mb-1.5">종료일</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-[15px] text-neutral-900 outline-none focus:border-neutral-400 focus:ring-2 focus:ring-neutral-200"
              required
            />
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-neutral-700 mb-1.5">리포트 유형</label>
          <div className="flex gap-2">
            {REPORT_TYPES.map((t) => (
              <button
                key={t.value}
                type="button"
                onClick={() => setReportType(t.value)}
                className={`rounded-lg border px-3 py-1.5 text-sm transition-colors ${
                  reportType === t.value
                    ? "border-neutral-900 bg-neutral-900 text-white"
                    : "border-neutral-200 bg-white text-neutral-600 hover:border-neutral-400"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-neutral-700 mb-2">분석 항목</label>
          <div className="flex flex-wrap gap-2">
            {METRICS.map((m) => {
              const checked = metrics.includes(m.value);
              return (
                <button
                  key={m.value}
                  type="button"
                  onClick={() => toggle(m.value)}
                  className={`flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm transition-colors ${
                    checked
                      ? "border-blue-200 bg-blue-50 text-blue-700"
                      : "border-neutral-200 bg-white text-neutral-500 hover:border-neutral-400"
                  }`}
                >
                  <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                    {checked ? (
                      <path d="M2 8.5l4 4 8-9" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                    ) : (
                      <rect x="2" y="2" width="12" height="12" rx="2" stroke="currentColor" strokeWidth="1.5" />
                    )}
                  </svg>
                  {m.label}
                </button>
              );
            })}
          </div>
        </div>

        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={!isValid || loading}
          className="rounded-lg bg-neutral-900 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-neutral-800 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {loading ? (
            <span className="flex items-center gap-2">
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
              생성 중...
            </span>
          ) : (
            "리포트 생성"
          )}
        </button>
      </form>

      {report && (
        <div className="mt-12 border-t border-neutral-200 pt-10">
          <div className="mb-6 flex items-center gap-2">
            <span className="rounded-md bg-green-50 px-2 py-0.5 text-xs font-medium text-green-700">생성 완료</span>
            <span className="text-sm text-neutral-500">{title}</span>
            {savedPath && (
              <Link
                href={`/logs/${savedPath}`}
                className="rounded-md bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700 hover:bg-blue-100 transition-colors"
              >
                저장된 리포트 보기
              </Link>
            )}
          </div>
          <MarkdownRenderer content={report} />
        </div>
      )}
    </div>
  );
}
