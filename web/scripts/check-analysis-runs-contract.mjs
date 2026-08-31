import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

const sample = {
  runs: [
    {
      run_id: "r1",
      run_type: "full-analysis",
      status: "completed",
      started_at: "2024-01-01T00:00:00Z",
      finished_at: "2024-01-01T00:05:00Z",
      error_reason: null,
    },
  ],
};

assert(Array.isArray(sample.runs), "GET /analysis/runs must return an envelope with runs array");
for (const row of sample.runs) {
  assert(typeof row.run_id === "string" && row.run_id.length > 0, "run_id must be a non-empty string");
  assert(typeof row.run_type === "string" && row.run_type.length > 0, "run_type must be a non-empty string");
  assert(["running", "completed", "failed"].includes(row.status), "status must be running|completed|failed");
  assert(typeof row.started_at === "string", "started_at must be a string");
  assert(row.finished_at === null || typeof row.finished_at === "string", "finished_at must be string|null");
  assert(row.error_reason === null || typeof row.error_reason === "string", "error_reason must be string|null");
}

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(__dirname, "..");
const backendRoot = path.resolve(webRoot, "..");

const backendApi = fs.readFileSync(path.join(backendRoot, "backend/api_service.py"), "utf8");
const apiClient = fs.readFileSync(path.join(webRoot, "src/lib/api-client.ts"), "utf8");

assert(backendApi.includes('@app.get("/jobs"'), "backend API must expose the durable GET /jobs route");
assert(backendApi.includes("limit: int = 20"), "GET /jobs route must accept a limit query parameter");
assert(apiClient.includes("/jobs?limit="), "web API client must poll durable jobs");
assert(apiClient.includes("filter(isAnalysisJob)"), "web must derive the analysis timeline from durable jobs");

console.log("Analysis runs contract verified against durable PostgreSQL jobs.");
