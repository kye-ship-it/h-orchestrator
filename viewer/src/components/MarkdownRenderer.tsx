"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import type { Components } from "react-markdown";

const components: Partial<Components> = {
  h1: ({ children, ...props }) => (
    <h1 className="mb-1 text-[32px] font-bold leading-tight text-neutral-900 first:mt-0 mt-10" {...props}>
      {children}
    </h1>
  ),
  h2: ({ children, ...props }) => (
    <h2 className="mt-10 mb-4 text-[22px] font-semibold text-neutral-800 border-b border-neutral-100 pb-2" {...props}>
      {children}
    </h2>
  ),
  h3: ({ children, ...props }) => (
    <h3 className="mt-7 mb-3 text-[17px] font-semibold text-neutral-800" {...props}>
      {children}
    </h3>
  ),
  p: ({ children, ...props }) => (
    <p className="my-2 text-[15px] leading-relaxed text-neutral-700" {...props}>
      {children}
    </p>
  ),
  blockquote: ({ children, ...props }) => (
    <blockquote
      className="my-4 rounded-r-md border-l-[3px] border-neutral-300 bg-neutral-50 py-2 px-4 text-[15px] text-neutral-600"
      {...props}
    >
      {children}
    </blockquote>
  ),
  table: ({ children, ...props }) => (
    <div className="my-5 overflow-x-auto rounded-lg border border-neutral-200">
      <table className="w-full border-collapse text-[14px]" {...props}>
        {children}
      </table>
    </div>
  ),
  thead: ({ children, ...props }) => (
    <thead className="bg-neutral-50 text-left text-[13px] font-medium text-neutral-500 uppercase tracking-wider" {...props}>
      {children}
    </thead>
  ),
  th: ({ children, ...props }) => (
    <th className="border-b border-neutral-200 px-4 py-2.5 font-medium" {...props}>
      {children}
    </th>
  ),
  td: ({ children, ...props }) => (
    <td className="border-b border-neutral-100 px-4 py-2.5 text-neutral-700" {...props}>
      {children}
    </td>
  ),
  tr: ({ children, ...props }) => (
    <tr className="hover:bg-neutral-50 transition-colors" {...props}>
      {children}
    </tr>
  ),
  ul: ({ children, ...props }) => (
    <ul className="my-2 ml-1 space-y-1 text-[15px] list-none" {...props}>
      {children}
    </ul>
  ),
  ol: ({ children, ...props }) => (
    <ol className="my-2 ml-5 space-y-1 text-[15px] list-decimal" {...props}>
      {children}
    </ol>
  ),
  li: ({ children, ...props }) => (
    <li className="text-neutral-700 leading-relaxed pl-1" {...props}>
      <span className="relative">
        {children}
      </span>
    </li>
  ),
  strong: ({ children, ...props }) => (
    <strong className="font-semibold text-neutral-900" {...props}>
      {children}
    </strong>
  ),
  code: ({ children, className, ...props }) => {
    if (!className) {
      return (
        <code className="rounded bg-neutral-100 px-1.5 py-0.5 text-[13px] font-mono text-red-600" {...props}>
          {children}
        </code>
      );
    }
    return <code className={className} {...props}>{children}</code>;
  },
  pre: ({ children, ...props }) => (
    <pre className="my-4 overflow-x-auto rounded-lg bg-neutral-900 p-4 text-[13px] text-neutral-100" {...props}>
      {children}
    </pre>
  ),
  a: ({ children, href, ...props }) => (
    <a
      href={href}
      className="text-blue-600 underline decoration-blue-200 underline-offset-2 hover:decoration-blue-400"
      target={href?.startsWith("http") ? "_blank" : undefined}
      rel={href?.startsWith("http") ? "noopener noreferrer" : undefined}
      {...props}
    >
      {children}
    </a>
  ),
  hr: (props) => <hr className="my-8 border-neutral-200" {...props} />,
  img: () => null,
};

export default function MarkdownRenderer({ content }: { content: string }) {
  return (
    <article className="max-w-none">
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]} components={components}>
        {content}
      </ReactMarkdown>
    </article>
  );
}
