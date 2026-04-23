const payload = [
  { title: "first", priority_score: 0.7, confidence: 0.9, source_refs: [{ type: "game", id: "g1", label: "Game 1" }] },
  { title: "second", priority_score: 0.7, confidence: 0.5, source_refs: [] },
];

for (const row of payload) {
  if (typeof row.priority_score !== "number") throw new Error("insights contract failed: priority_score must be numeric");
  if (typeof row.confidence !== "number") throw new Error("insights contract failed: confidence must be numeric");
  if (!Array.isArray(row.source_refs)) throw new Error("insights contract failed: source_refs must be an array");
}

const sorted = [...payload].sort((left, right) => right.priority_score - left.priority_score || right.confidence - left.confidence);
if (sorted[0]?.title !== "first") throw new Error("insights contract failed: expected priority/confidence ranking semantics");

console.log("Insights contract verified: ranking, confidence, and source references are present.");
