function assert(condition, message) {
  if (!condition) throw new Error(message);
}

const payload = {
  pivot: "month",
  buckets: [{ bucket: "2024-01", total_games: 3 }],
  totals: { total_games: 3 },
};

assert(["month", "result", "compliance"].includes(payload.pivot), "pivot must be enum");
assert(Array.isArray(payload.buckets), "buckets must be array");
assert(typeof payload.totals === "object" && payload.totals !== null, "totals must exist");

console.log("Time usage contract verified.");
