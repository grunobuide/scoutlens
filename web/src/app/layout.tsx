import type { Metadata } from "next";
import type { ReactNode } from "react";
import "@fontsource-variable/inter";
import "./globals.css";

import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";

export const metadata: Metadata = {
  title: {
    default: "ScoutLens — Player Fingerprints",
    template: "%s — ScoutLens",
  },
  description:
    "An evidence-first exploration of stable statistical fingerprints in football event data.",
  applicationName: "ScoutLens",
  keywords: ["football analytics", "data science", "player fingerprints", "reproducible research"],
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>
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
