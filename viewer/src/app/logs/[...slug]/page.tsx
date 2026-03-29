import { notFound } from "next/navigation";
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

  return <LogViewer filePath={filePath} initialContent={rawContent} />;
}
