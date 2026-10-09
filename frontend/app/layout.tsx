import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Candidate True Companion",
  description: "Resume in, one realistic interview, useful feedback out.",
};

// Visual direction locked 2026-09-01 (see docs/Architecture-Decisions.md §8).
// Change this single value to switch the whole app's visual identity.
const ACTIVE_BRAND = "momentum";

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" data-brand={ACTIVE_BRAND}>
      <body>{children}</body>
    </html>
  );
}
