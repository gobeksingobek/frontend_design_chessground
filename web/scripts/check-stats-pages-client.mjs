import { readFileSync } from "node:fs";

const files = [
  "src/app/(app)/insights/page.tsx",
  "src/app/(app)/lines/page.tsx",
  "src/app/(app)/rating-bands/page.tsx",
  "src/app/(app)/review/page.tsx",
  "src/app/(app)/time-usage/page.tsx",
];

const missingDirective = files.filter((file) => {
  const source = readFileSync(new URL(`../${file}`, import.meta.url), "utf8");
  const firstCodeLine = source
    .split(/\r?\n/u)
    .map((line) => line.trim())
    .find((line) => line.length > 0 && !line.startsWith("//"));

  return firstCodeLine !== '"use client";';
});

if (missingDirective.length > 0) {
  console.error("The following stats pages must start with \"use client\" to pass queryFn props:");
  for (const file of missingDirective) {
    console.error(`- ${file}`);
  }
  process.exit(1);
}

console.log("Verified stats pages are marked as client components.");
