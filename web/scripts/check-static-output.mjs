import { readFile, readdir } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const webRoot = resolve(scriptDirectory, "..");
const routes = ["index.html", "lab/index.html", "science/index.html"];
const landmarks = ["<header", "<nav", "<main", "<footer"];

for (const route of routes) {
  const html = await readFile(resolve(webRoot, "out", route), "utf8");
  for (const landmark of landmarks) {
    if (!html.includes(landmark)) {
      throw new Error(`${route} is missing semantic landmark ${landmark}`);
    }
  }
}

async function assertStaticOnly(directory) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) {
      await assertStaticOnly(path);
      continue;
    }
    if (/^route\.[cm]?[jt]sx?$/.test(entry.name)) {
      throw new Error(`Runtime route handler is not allowed: ${path}`);
    }
    if (/\.[jt]sx?$/.test(entry.name)) {
      const source = await readFile(path, "utf8");
      if (/^[\t ]*["']use server["'];?/m.test(source)) {
        throw new Error(`Server action is not allowed: ${path}`);
      }
    }
  }
}

await assertStaticOnly(resolve(webRoot, "src", "app"));
console.log("Static export contains all routes and semantic landmarks");
