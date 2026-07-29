import { createReadStream } from "node:fs";
import { stat } from "node:fs/promises";
import { createServer } from "node:http";
import { dirname, extname, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { createGzip } from "node:zlib";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const outputRoot = resolve(scriptDirectory, "..", "out");
const portArgument = process.argv.indexOf("--port");
const port = Number(portArgument === -1 ? 4173 : process.argv[portArgument + 1]);
if (!Number.isInteger(port) || port < 1 || port > 65535) {
  throw new Error(`Invalid port: ${process.argv[portArgument + 1] ?? ""}`);
}

const contentTypes = new Map([
  [".css", "text/css; charset=utf-8"],
  [".html", "text/html; charset=utf-8"],
  [".js", "text/javascript; charset=utf-8"],
  [".json", "application/json; charset=utf-8"],
  [".svg", "image/svg+xml"],
  [".txt", "text/plain; charset=utf-8"],
  [".woff2", "font/woff2"],
]);
const compressible = new Set([".css", ".html", ".js", ".json", ".svg", ".txt"]);

function cacheControl(pathname) {
  if (pathname === "/showcase/v1/manifest.json") {
    return "public, max-age=60, must-revalidate";
  }
  if (pathname.startsWith("/_next/static/") || pathname.startsWith("/showcase/v1/")) {
    return "public, max-age=31536000, immutable";
  }
  if (pathname.endsWith(".html") || pathname.endsWith("/")) {
    return "no-cache";
  }
  return "public, max-age=3600";
}

async function fileFor(pathname) {
  const decoded = decodeURIComponent(pathname);
  const relative = decoded === "/" ? "index.html" : decoded.replace(/^\/+/, "");
  const candidates = relative.endsWith("/")
    ? [`${relative}index.html`]
    : extname(relative) === ""
      ? [relative, `${relative}/index.html`]
      : [relative];
  for (const candidate of candidates) {
    const path = resolve(outputRoot, candidate);
    if (path !== outputRoot && !path.startsWith(`${outputRoot}${sep}`)) {
      return null;
    }
    try {
      if ((await stat(path)).isFile()) {
        return path;
      }
    } catch (error) {
      if (error?.code !== "ENOENT") {
        throw error;
      }
    }
  }
  return null;
}

const server = createServer(async (request, response) => {
  try {
    if (request.method !== "GET" && request.method !== "HEAD") {
      response.writeHead(405, { Allow: "GET, HEAD" }).end();
      return;
    }
    const url = new URL(request.url ?? "/", "http://127.0.0.1");
    const path = await fileFor(url.pathname);
    if (path === null) {
      response.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" }).end("Not found");
      return;
    }

    const extension = extname(path).toLowerCase();
    const useGzip =
      compressible.has(extension) && /(?:^|,)\s*gzip\s*(?:,|$)/i.test(request.headers["accept-encoding"] ?? "");
    response.setHeader("Cache-Control", cacheControl(url.pathname));
    response.setHeader("Content-Type", contentTypes.get(extension) ?? "application/octet-stream");
    response.setHeader("Referrer-Policy", "strict-origin-when-cross-origin");
    response.setHeader("X-Content-Type-Options", "nosniff");
    if (useGzip) {
      response.setHeader("Content-Encoding", "gzip");
      response.setHeader("Vary", "Accept-Encoding");
    }
    if (request.method === "HEAD") {
      response.writeHead(200).end();
      return;
    }
    response.writeHead(200);
    const stream = createReadStream(path);
    stream.on("error", (error) => response.destroy(error));
    if (useGzip) {
      stream.pipe(createGzip({ level: 9 })).pipe(response);
    } else {
      stream.pipe(response);
    }
  } catch (error) {
    console.error(error);
    if (!response.headersSent) {
      response.writeHead(500, { "Content-Type": "text/plain; charset=utf-8" });
    }
    response.end("Internal server error");
  }
});

server.listen(port, "127.0.0.1", () => {
  console.log(`ScoutLens static server listening at http://127.0.0.1:${port}`);
});

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => server.close(() => process.exit(0)));
}
