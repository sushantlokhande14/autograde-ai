import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { GraphQLProvider } from "@/lib/apollo";

export const metadata: Metadata = {
  title: "Autograde AI",
  description: "Local-first, multi-agent grading platform for CS coursework.",
};

const nav = [
  { href: "/", label: "Overview" },
  { href: "/review", label: "Review queue" },
  { href: "/audit", label: "Grade audit" },
  { href: "/rubric", label: "Rubric" },
  { href: "/health", label: "System health" },
];

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <div className="flex min-h-screen">
          <aside className="w-52 shrink-0 border-r border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-900">
            <p className="px-2 text-lg font-semibold tracking-tight">Autograde AI</p>
            <nav className="mt-6 space-y-1">
              {nav.map((n) => (
                <Link
                  key={n.href}
                  href={n.href}
                  className="block rounded-lg px-2 py-1.5 text-sm text-neutral-700 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800"
                >
                  {n.label}
                </Link>
              ))}
            </nav>
          </aside>
          <main className="min-w-0 flex-1">
            <GraphQLProvider>{children}</GraphQLProvider>
          </main>
        </div>
      </body>
    </html>
  );
}
