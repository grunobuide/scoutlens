import { spawn } from "node:child_process";

import { chromium } from "@playwright/test";

const pnpmCli = process.env.npm_execpath;
if (pnpmCli === undefined) {
  throw new Error("Run this gate through pnpm so the pinned LHCI binary can be resolved");
}

const lhci = spawn(process.execPath, [pnpmCli, "exec", "lhci", "autorun"], {
  env: {
    ...process.env,
    CHROME_PATH: chromium.executablePath(),
  },
  stdio: "inherit",
  windowsHide: true,
});
lhci.once("error", (error) => {
  throw error;
});
lhci.once("exit", (code) => {
  process.exitCode = code ?? 1;
});
