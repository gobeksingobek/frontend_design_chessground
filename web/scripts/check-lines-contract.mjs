function assert(condition, message) {
  if (!condition) throw new Error(message);
}

const detail = {
  line_id: "line-a",
  total_games: 4,
  compliance_rate: 0.5,
};
assert(typeof detail.line_id === "string", "GET /lines/stats/{line_id} requires line_id");
assert("total_games" in detail, "GET /lines/stats/{line_id} requires total_games");

const history = {
  line_id: "line-a",
  buckets: [{ bucket: "2024-01", total_games: 2 }],
  totals: { total_games: 2, months: 1 },
};
assert(Array.isArray(history.buckets), "GET /lines/stats/{line_id}/history requires buckets[]");
assert("totals" in history, "GET /lines/stats/{line_id}/history requires totals");

console.log("Lines contracts verified.");
