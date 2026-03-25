"use client";

import { useState } from "react";
import MarkdownRenderer from "@/components/MarkdownRenderer";

const REPORT_TYPES = [
  { value: "trend", label: "Trend Analysis" },
  { value: "comparison", label: "Comparison" },
  { value: "executive", label: "Executive Summary" },
];

const METRICS = [
  { value: "calls", label: "Calls" },
  { value: "bant", label: "BANT" },
  { value: "duration", label: "Duration" },
  { value: "transfers", label: "Transfers" },
];

export default function GenerateReportPage() {
  const [title, setTitle] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [reportType, setReportType] = useState("trend");
  const [metrics, setMetrics] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const toggle = (m: string) =>
    setMetrics((prev) => (prev.includes(m) ? prev.filter((x) => x !== m) : [...prev, m]));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setReport(null);

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
      setReport(data.content ?? data.report ?? "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setLoading(false);
    }
  };

  const isValid = title.trim() && startDate && endDate && metrics.length > 0;

  return (
    <div>
      <h1 className="text-[26px] font-bold text-neutral-900 mb-1">Generate Report</h1>
      <p className="text-sm text-neutral-500 mb-8">Create an on-demand analysis report from call log data</p>

      <form onSubmit={handleSubmit} className="space-y-6 max-w-lg">
        {/* Title */}
        <div>
          <label className="block text-sm font-medium text-neutral-700 mb-1.5">Title</label>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Weekly Performance Report"
            className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-[15px] text-neutral-900 placeholder:text-neutral-400 outline-none focus:border-neutral-400 focus:ring-2 focus:ring-neutral-200"
            required
          />
        </div>

        {/* Date Range */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-neutral-700 mb-1.5">Start Date</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-[15px] text-neutral-900 outline-none focus:border-neutral-400 focus:ring-2 focus:ring-neutral-200"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-neutral-700 mb-1.5">End Date</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-[15px] text-neutral-900 outline-none focus:border-neutral-400 focus:ring-2 focus:ring-neutral-200"
              required
            />
          </div>
        </div>

        {/* Report Type */}
        <div>
          <label className="block text-sm font-medium text-neutral-700 mb-1.5">Report Type</label>
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

        {/* Metrics */}
        <div>
          <label className="block text-sm font-medium text-neutral-700 mb-2">Metrics to include</label>
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
              Generating...
            </span>
          ) : (
            "Generate Report"
          )}
        </button>
      </form>

      {report && (
        <div className="mt-12 border-t border-neutral-200 pt-10">
          <div className="mb-6 flex items-center gap-2">
            <span className="rounded-md bg-green-50 px-2 py-0.5 text-xs font-medium text-green-700">Generated</span>
            <span className="text-sm text-neutral-500">{title}</span>
          </div>
          <MarkdownRenderer content={report} />
        </div>
      )}
    </div>
  );
}
