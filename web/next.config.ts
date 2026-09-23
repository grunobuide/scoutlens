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

// SCOUTLENS_BASE_PATH serves the export from a subpath instead of the origin
// root (scoutlens-jtt.7.2). GitHub Pages for a project repository serves at
// `/<repo>/`, and every asset reference this export emits is root-absolute, so
// without it the deployed site 404s on its own JavaScript.
//
// Opt-in rather than hard-coded: the default build, every unit test and the
// whole e2e suite run at the root, and a base path baked in would make local
// development differ from what CI checks. Next derives `assetPrefix` from
// `basePath` for a static export, so setting one is enough.
const basePath = process.env.SCOUTLENS_BASE_PATH?.trim() || undefined;

const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  ...(distDir === undefined ? {} : { distDir }),
  ...(basePath === undefined ? {} : { basePath }),
  images: {
    unoptimized: true,
  },
  poweredByHeader: false,
};

export default nextConfig;
