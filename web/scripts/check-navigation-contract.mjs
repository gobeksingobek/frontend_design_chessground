import fs from "node:fs";
import path from "node:path";

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

const source = fs.readFileSync(
  path.resolve("src/components/app-shell.tsx"),
  "utf8",
);
const appLayout = fs.readFileSync(path.resolve("src/app/(app)/layout.tsx"), "utf8");
const legacyLoginPage = fs.readFileSync(path.resolve("src/app/login/page.tsx"), "utf8");

for (const route of ["/overview", "/analysis", "/tree", "/trainer"]) {
  assert(source.includes(`href: "${route}"`), `Sidebar is missing ${route}`);
}

assert(!source.includes('from "next/link"'), "Sidebar navigation must not depend on Next Link hydration");
assert(/<a\r?\n\s+key=\{item\.href\}/.test(source), "Sidebar items must be native anchors");
assert(source.includes("if (!hydrated)"), "App shell must wait for client hydration before rendering interactive state");
assert(!source.includes('href="/login"'), "App shell must not expose a login route");
assert(!appLayout.includes("AuthGate"), "Dashboard routes must render without a browser auth gate");
assert(legacyLoginPage.includes('redirect("/overview")'), "Legacy login URLs must redirect to the dashboard");

console.log("Sidebar navigation contract verified.");
