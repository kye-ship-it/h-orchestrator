import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "HMCA Monitor",
  description: "H-Orchestrator Agent Monitoring System",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} h-full`}>
      <body className="h-full bg-white text-neutral-900 font-[family-name:var(--font-inter)] antialiased">
        <div className="flex h-full">
          <Sidebar />
          <main className="flex-1 overflow-y-auto">
            <div className="mx-auto max-w-[900px] px-12 py-10">{children}</div>
          </main>
        </div>
      </body>
    </html>
  );
}
