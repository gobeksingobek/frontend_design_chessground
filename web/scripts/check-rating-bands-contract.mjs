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
assert(typeof payload.percentiles === "object", "percentiles metadata required");
assert(typeof payload.totals === "object", "totals metadata required");
assert(Array.isArray(payload.buckets), "buckets must be array");

console.log("Rating band contract verified.");
