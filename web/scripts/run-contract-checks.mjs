import { readdir } from "node:fs/promises";
import path from "node:path";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

const scriptsDirectory = path.resolve(fileURLToPath(new URL(".", import.meta.url)));
const checks = (await readdir(scriptsDirectory))
  .filter((name) => /^check-.*\.mjs$/i.test(name))
  .sort();

if (checks.length === 0) {
  console.error("No contract checks were found under web/scripts.");
  process.exit(1);
}

for (const check of checks) {
  const exitCode = await new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [path.join(scriptsDirectory, check)], {
      cwd: path.dirname(scriptsDirectory),
      stdio: "inherit",
    });
    child.on("error", reject);
    child.on("exit", (code, signal) => {
      if (signal) {
        reject(new Error(`${check} terminated by ${signal}`));
        return;
      }
      resolve(code ?? 1);
    });
  });
  if (exitCode !== 0) {
    process.exit(exitCode);
  }
}

console.log(`All ${checks.length} frontend contract checks passed.`);
