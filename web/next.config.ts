import path from "node:path";

import type { NextConfig } from "next";

// SCOUTLENS_DIST_DIR isolates the test-only fixture export build (scoutlens-uze.7)
// from the production `.next`/`out`; production builds leave it unset.
// Next.js joins `distDir` onto the project directory, so an absolute Windows
// path must be converted to a relative one before it is handed to the config.
const distDir =
  process.env.SCOUTLENS_DIST_DIR === undefined
    ? undefined
    : path.relative(process.cwd(), process.env.SCOUTLENS_DIST_DIR).replaceAll("\\", "/");

const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  ...(distDir === undefined ? {} : { distDir }),
  images: {
    unoptimized: true,
  },
  poweredByHeader: false,
};

export default nextConfig;
