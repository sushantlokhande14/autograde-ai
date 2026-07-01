import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Autograde AI",
  description: "Local-first, agent-orchestrated grading platform for CS coursework.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
