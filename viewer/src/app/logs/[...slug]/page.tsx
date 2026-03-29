import { notFound } from "next/navigation";
import matter from "gray-matter";
import { readFile } from "@/lib/gcs";
import LogViewer from "./LogViewer";

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

  return (
    <LogViewer
      filePath={filePath}
      initialRaw={rawContent}
      initialContent={content}
      frontmatter={Object.fromEntries(
        Object.entries(frontmatter).map(([k, v]) => [k, String(v)])
      )}
    />
  );
}
