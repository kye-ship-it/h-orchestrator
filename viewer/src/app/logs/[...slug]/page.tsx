import { notFound } from "next/navigation";
import matter from "gray-matter";
import { readFile } from "@/lib/gcs";
import MarkdownRenderer from "@/components/MarkdownRenderer";

export const dynamic = "force-dynamic";

export default async function LogPage({
  params,
}: {
  params: Promise<{ slug: string[] }>;
}) {
  const { slug } = await params;
  const filePath = slug.join("/");

  const rawContent = await readFile(filePath);
  if (!rawContent) notFound();

  const { data: frontmatter, content } = matter(rawContent);

  // Build breadcrumb from path
  const pathParts = filePath.replace(/\.md$/, "").split("/");

  return (
    <div>
      {/* Breadcrumb */}
      <div className="mb-6 flex items-center gap-1.5 text-sm text-neutral-400">
        {pathParts.map((part, i) => (
          <span key={i} className="flex items-center gap-1.5">
            {i > 0 && <span>/</span>}
            <span className={i === pathParts.length - 1 ? "text-neutral-600" : ""}>
              {part}
            </span>
          </span>
        ))}
      </div>

      {/* Meta badges */}
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
        {frontmatter.period && (
          <span className="rounded-md bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700">
            {String(frontmatter.period)}
          </span>
        )}
      </div>

      <MarkdownRenderer content={content} />
    </div>
  );
}
