import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "..");

const backendApiPath = path.join(repoRoot, "../backend/api_service.py");
const apiClientPath = path.join(repoRoot, "src/lib/api-client.ts");

const backendApi = fs.readFileSync(backendApiPath, "utf8");
const apiClient = fs.readFileSync(apiClientPath, "utf8");

const canonicalRoutes = ["/lines/stats/{line_id}", "/lines/stats/{line_id}/history"];
for (const route of canonicalRoutes) {
  assert(backendApi.includes(`@app.get("${route}"`), `Missing canonical backend route: ${route}`);
}

const forbiddenBackendAliases = [
  '@app.get("/lines/{line_id}"',
  '@app.get("/lines/{line_id}/history"',
  '@app.get("/lines/{line_id}/stats"',
];
for (const alias of forbiddenBackendAliases) {
  assert(!backendApi.includes(alias), `Forbidden backend alias route found: ${alias}`);
}

assert(apiClient.includes("/lines/stats/${encodeURIComponent(lineId)}"), "Client must call canonical /lines/stats/{line_id} detail route.");
assert(
  apiClient.includes("/lines/stats/${encodeURIComponent(lineId)}/history"),
  "Client must call canonical /lines/stats/{line_id}/history route.",
);

const forbiddenClientAliases = ["${API_BASE_URL}/lines/${encodeURIComponent(lineId)}", "${API_BASE_URL}/lines/${encodeURIComponent(lineId)}/history"];
for (const alias of forbiddenClientAliases) {
  assert(!apiClient.includes(alias), `Forbidden client alias route found: ${alias}`);
}

console.log("Lines contracts verified: canonical /lines/stats/{line_id} and /lines/stats/{line_id}/history only; no /lines/{line_id} aliasing.");
