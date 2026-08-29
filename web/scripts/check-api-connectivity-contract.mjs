import fs from "node:fs";
import path from "node:path";

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

const source = fs.readFileSync(path.resolve("src/lib/api-client.ts"), "utf8");

assert(source.includes("async function apiFetch"), "API client must centralize transport errors");
assert(source.includes("Unable to reach the ChessGround API"), "Network failures must explain the failed API connection");
assert(source.includes("API_CORS_ORIGINS"), "Network failures must include CORS remediation guidance");
assert(!source.includes("await fetch(`${API_BASE_URL}"), "All API calls must use the transport wrapper");

console.log("API connectivity contract verified.");
