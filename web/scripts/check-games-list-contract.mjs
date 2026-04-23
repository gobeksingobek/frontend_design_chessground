import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function checkGamesResponseShape(payload) {
  assert(Array.isArray(payload), "GET /games payload must be an array");
  for (const row of payload) {
    assert(row !== null && typeof row === "object", "Each GET /games row must be an object");
    assert(Number.isInteger(row.id), "Each GET /games row must include integer id");
    assert(row.date === null || typeof row.date === "string", "Each GET /games row date must be string|null");
    assert(row.result === null || typeof row.result === "string", "Each GET /games row result must be string|null");
    assert(row.compliance === null || typeof row.compliance === "string", "Each GET /games row compliance must be string|null");
    assert(row.line_id === null || typeof row.line_id === "string", "Each GET /games row line_id must be string|null");
  }
}

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(__dirname, "..");
const backendRoot = path.resolve(webRoot, "..");

const backendApi = fs.readFileSync(path.join(backendRoot, "backend/api_service.py"), "utf8");
const backendReadApi = fs.readFileSync(path.join(backendRoot, "backend/read_api.py"), "utf8");
const apiClient = fs.readFileSync(path.join(webRoot, "src/lib/api-client.ts"), "utf8");

for (const param of ["date_from", "date_to", "result", "compliance_min", "line_id", "player", "sort_by", "sort_dir"]) {
  assert(backendApi.includes(`${param}:`), `Missing GET /games query parameter in backend/api_service.py: ${param}`);
  assert(apiClient.includes(`search.set(\"${param}\"`), `Missing client forwarding for GET /games query parameter: ${param}`);
}

assert(backendReadApi.includes('sort_by: str = "date"'), "read_api fetch_games default sort_by must be date");
assert(backendReadApi.includes('sort_dir: str = "desc"'), "read_api fetch_games default sort_dir must be desc");

checkGamesResponseShape([
  {
    id: 42,
    date: "2024.01.01",
    white: "Alpha",
    black: "Beta",
    result: "1-0",
    line_id: "line-a",
    compliance: "FULLY_COMPLIANT",
    max_matched_ply: 20,
  },
]);

console.log("Games list contract verified for query controls, default ordering config, and response shape.");
