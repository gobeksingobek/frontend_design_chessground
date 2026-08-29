import fs from "node:fs";
import path from "node:path";

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

const source = fs.readFileSync(
  path.resolve("src/components/app-shell.tsx"),
  "utf8",
);

for (const route of ["/overview", "/analysis", "/tree", "/trainer"]) {
  assert(source.includes(`href: "${route}"`), `Sidebar is missing ${route}`);
}

assert(!source.includes('from "next/link"'), "Sidebar navigation must not depend on Next Link hydration");
assert(source.includes("<a\n                          key={item.href}"), "Sidebar items must be native anchors");
assert(source.includes("if (!hydrated)"), "App shell must wait for client hydration before rendering interactive state");

console.log("Sidebar navigation contract verified.");
