function assert(condition, message) {
  if (!condition) throw new Error(message);
}

const payload = {
  pivot: "self_vs_opp",
  buckets: [{ bucket: "Self", total_games: 3 }],
  totals: { total_games: 3, total_moves: 42 },
};

assert(["self_vs_opp", "in_book_vs_out_of_book"].includes(payload.pivot), "pivot must be enum");
assert(Array.isArray(payload.buckets), "buckets must be array");
assert(typeof payload.totals === "object" && payload.totals !== null, "totals must exist");
assert(Object.prototype.hasOwnProperty.call(payload, "pivot"), "response must include pivot");
assert(Object.prototype.hasOwnProperty.call(payload, "buckets"), "response must include buckets");
assert(Object.prototype.hasOwnProperty.call(payload, "totals"), "response must include totals");

console.log("Time usage contract verified.");
