import fs from "node:fs";
import path from "node:path";

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

const source = fs.readFileSync(
  path.resolve("src/app/api/backend/[...path]/route.ts"),
  "utf8",
);
const clientSource = fs.readFileSync(path.resolve("src/lib/api-client.ts"), "utf8");

for (const header of ["authorization", "content-type", "idempotency-key"]) {
  assert(source.includes(`"${header}"`), `Proxy must forward ${header}`);
}
for (const method of ["GET", "POST", "PUT", "PATCH", "DELETE"]) {
  assert(source.includes(`export const ${method} = proxy`), `Proxy must handle ${method}`);
}
assert(source.includes("API_BASE_URL"), "Proxy must use the server-only API_BASE_URL");
assert(source.includes("UPSTREAM_UNAVAILABLE"), "Proxy must return a readable upstream failure");
assert(source.includes("request.arrayBuffer()"), "Proxy must preserve multipart request bodies");
assert(
  clientSource.includes('const API_BASE_URL = "/api/backend";'),
  "Browser API calls must always use the same-origin proxy",
);
assert(
  !clientSource.includes("NEXT_PUBLIC_API_BASE_URL"),
  "A public environment variable must not bypass the same-origin proxy",
);

console.log("API proxy contract verified.");
