import { readdir } from "node:fs/promises";
import path from "node:path";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

const projectRoot = path.resolve(fileURLToPath(new URL("..", import.meta.url)));
const srcRoot = path.join(projectRoot, "src");

async function collectTests(dir) {
  const entries = await readdir(dir, { withFileTypes: true });
  const files = [];

  for (const entry of entries) {
    const entryPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await collectTests(entryPath)));
      continue;
    }

    if (/\.test\.tsx?$/i.test(entry.name)) {
      files.push(entryPath);
    }
  }

  return files;
}

const testFiles = (await collectTests(srcRoot)).sort();

if (testFiles.length === 0) {
  console.error("No UI regression test files were found under web/src.");
  process.exit(1);
}

const args = ["--test", "--loader", "./scripts/node-test-ts-loader.mjs", ...testFiles];
const child = spawn(process.execPath, args, {
  cwd: projectRoot,
  stdio: "inherit",
});

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 1);
});
