import { Suspense } from "react";
import SearchContent from "@/components/SearchContent";

export default function SearchPage() {
  return (
    <Suspense
      fallback={
        <div className="space-y-6">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Search Logs</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Search across all log files and reports.
            </p>
          </div>
          <div className="h-8 w-full max-w-lg animate-pulse rounded-lg bg-muted" />
        </div>
      }
    >
      <SearchContent />
    </Suspense>
  );
}
