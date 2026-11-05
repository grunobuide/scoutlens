import type { Metadata } from "next";
import localFont from "next/font/local";
import type { ReactNode } from "react";
import "./globals.css";

import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";

const inter = localFont({
  display: "swap",
  fallback: ["Inter", "Arial", "sans-serif"],
  src: [
    {
      path: "../../node_modules/@fontsource-variable/inter/files/inter-latin-wght-normal.woff2",
      style: "normal",
      weight: "100 900",
    },
    {
      path: "../../node_modules/@fontsource-variable/inter/files/inter-latin-ext-wght-normal.woff2",
      style: "normal",
      weight: "100 900",
    },
  ],
  variable: "--font-inter",
});

// Display face for h1 and h2 (`scoutlens-rdz.5`). The wght-only files are
// instanced at the family's default optical size, 96, the display cut; the
// opsz-axis files add 48 KB for optical sizing that only small text needs.
const display = localFont({
  display: "swap",
  fallback: ["Inter", "Arial", "sans-serif"],
  src: [
    {
      path: "../../node_modules/@fontsource-variable/bricolage-grotesque/files/bricolage-grotesque-latin-wght-normal.woff2",
      style: "normal",
      weight: "200 800",
    },
    {
      path: "../../node_modules/@fontsource-variable/bricolage-grotesque/files/bricolage-grotesque-latin-ext-wght-normal.woff2",
      style: "normal",
      weight: "200 800",
    },
  ],
  variable: "--font-display",
});

// Mono face for code, kbd, samp and pre (`scoutlens-rdz.5`). Not preloaded:
// none of it is above the fold, so it loads on first use instead of competing
// with the LCP text.
const mono = localFont({
  adjustFontFallback: false,
  display: "swap",
  fallback: ["ui-monospace", "Consolas", "monospace"],
  preload: false,
  src: [
    {
      path: "../../node_modules/@fontsource-variable/jetbrains-mono/files/jetbrains-mono-latin-wght-normal.woff2",
      style: "normal",
      weight: "100 800",
    },
    {
      path: "../../node_modules/@fontsource-variable/jetbrains-mono/files/jetbrains-mono-latin-ext-wght-normal.woff2",
      style: "normal",
      weight: "100 800",
    },
  ],
  variable: "--font-mono",
});

export const metadata: Metadata = {
  title: {
    default: "Yumusarái Labs — Player Fingerprints",
    template: "%s — Yumusarái Labs",
  },
  description:
    "An evidence-first exploration of stable statistical fingerprints in football event data.",
  applicationName: "Yumusarái Labs",
  keywords: ["football analytics", "data science", "player fingerprints", "reproducible research"],
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${inter.variable} ${display.variable} ${mono.variable}`}>
        <a className="skip-link" href="#main-content">
          Skip to content
        </a>
        <SiteHeader />
        {children}
        <SiteFooter />
      </body>
    </html>
  );
}
