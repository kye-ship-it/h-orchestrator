import matter from "gray-matter";
import { readFile, getLatestDailyLog } from "@/lib/gcs";
import MarkdownRenderer from "@/components/MarkdownRenderer";

export const dynamic = "force-dynamic";

export default async function Home() {
  const latest = await getLatestDailyLog();

  if (!latest) {
    return (
      <div className="py-16 text-center">
        <div className="mx-auto mb-6 flex h-14 w-14 items-center justify-center rounded-full bg-neutral-100">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
            <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2" stroke="#9ca3af" strokeWidth="1.5" />
            <rect x="9" y="3" width="6" height="4" rx="1" stroke="#9ca3af" strokeWidth="1.5" />
            <path d="M9 12h6M9 16h4" stroke="#9ca3af" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </div>
        <h1 className="text-xl font-semibold text-neutral-800">Welcome to HMCA Monitor</h1>
        <p className="mt-2 text-[15px] text-neutral-500 max-w-md mx-auto">
          No reports generated yet. Configure your GCS bucket and run the pipeline to start seeing daily logs here.
        </p>
        <div className="mt-8 rounded-lg border border-neutral-200 bg-neutral-50 p-5 text-left max-w-sm mx-auto">
          <p className="text-sm font-medium text-neutral-700 mb-3">Quick Start</p>
          <ol className="space-y-2 text-sm text-neutral-600">
            <li className="flex gap-2">
              <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-neutral-200 text-xs font-medium">1</span>
              Set <code className="rounded bg-neutral-200 px-1 text-xs font-mono">GCS_BUCKET</code> in env
            </li>
            <li className="flex gap-2">
              <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-neutral-200 text-xs font-medium">2</span>
              Run the pipeline to generate reports
            </li>
            <li className="flex gap-2">
              <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-neutral-200 text-xs font-medium">3</span>
              Reports appear automatically in sidebar
            </li>
          </ol>
        </div>
      </div>
    );
  }

  const { data: frontmatter, content } = matter(latest.content);

  return (
    <div>
      {/* Breadcrumb */}
      <div className="mb-6 flex items-center gap-1.5 text-sm text-neutral-400">
        <span>Daily Logs</span>
        <span>/</span>
        <span className="text-neutral-600">{String(frontmatter.date || "Latest")}</span>
      </div>

      {/* Meta */}
      <div className="mb-8 flex flex-wrap items-center gap-2">
        {frontmatter.date && (
          <span className="rounded-md bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700">
            {String(frontmatter.date)}
          </span>
        )}
        {frontmatter.agent && (
          <span className="rounded-md bg-neutral-100 px-2 py-0.5 text-xs font-medium text-neutral-600">
            {String(frontmatter.agent)}
          </span>
        )}
        {frontmatter.type && (
          <span className="rounded-md bg-neutral-100 px-2 py-0.5 text-xs font-medium text-neutral-600">
            {String(frontmatter.type)}
          </span>
        )}
      </div>

      <MarkdownRenderer content={content} />
    </div>
  );
}
