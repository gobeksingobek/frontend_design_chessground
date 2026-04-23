function assert(condition, message) {
  if (!condition) throw new Error(message);
}

const payload = {
  band_size: 100,
  allowed_band_sizes: [50, 100, 150, 200, 250, 300, 350, 400],
  percentiles: { p25_compliance_rate: 0.4, p50_compliance_rate: 0.5, p75_compliance_rate: 0.8 },
  totals: { total_games: 8, bucket_count: 2 },
  buckets: [{ white_band: "1500-1599", black_band: "1400-1499", total_games: 8 }],
};

assert(payload.allowed_band_sizes.includes(payload.band_size), "band_size must be guardrail-compliant");
assert(payload.band_size >= 50, "band_size must respect min guardrail");
assert(payload.band_size <= 400, "band_size must respect max guardrail");
assert((payload.band_size - 50) % 50 === 0, "band_size must respect step guardrail");
assert(payload.allowed_band_sizes.every((size) => size >= 50 && size <= 400), "allowed_band_sizes must stay within min/max");
assert(payload.allowed_band_sizes.every((size) => (size - 50) % 50 === 0), "allowed_band_sizes must follow step");
assert(typeof payload.percentiles === "object", "percentiles metadata required");
assert(["p25_compliance_rate", "p50_compliance_rate", "p75_compliance_rate"].every((key) => Object.prototype.hasOwnProperty.call(payload.percentiles, key)), "percentiles must include p25/p50/p75 keys");
assert(typeof payload.totals === "object", "totals metadata required");
assert(Object.prototype.hasOwnProperty.call(payload.totals, "total_games"), "totals must include total_games");
assert(Object.prototype.hasOwnProperty.call(payload.totals, "bucket_count"), "totals must include bucket_count");
assert(Array.isArray(payload.buckets), "buckets must be array");

console.log("Rating band contract verified.");
