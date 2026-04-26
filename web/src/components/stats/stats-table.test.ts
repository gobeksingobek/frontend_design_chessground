import test from "node:test";
import assert from "node:assert/strict";

import {
  buildRatingBandSummary,
  normalizeBandSizeByGuardrails,
  normalizeStatsRows,
  resolveColumns,
  resolveDetailTab,
  resolveSelectedRowId,
  resolveSelectedRowIndex,
  summarizePivot,
} from "./stats-table-helpers.ts";

test("drill-down row normalization supports bucket payload", () => {
  const rows = normalizeStatsRows({ buckets: [{ bucket: "2024-01", total_games: 2 }] });
  assert.equal(rows.length, 1);
  assert.equal(rows[0].bucket, "2024-01");
});

test("row selection clamps to available rows", () => {
  assert.equal(resolveSelectedRowIndex(3, 2), 1);
  assert.equal(resolveSelectedRowIndex(-1, 2), 0);
  assert.equal(resolveSelectedRowIndex(0, 0), 0);
});

test("row selection resolves row id from configured field", () => {
  assert.equal(resolveSelectedRowId({ key: "line-a" }, "key"), "line-a");
  assert.equal(resolveSelectedRowId({ line_id: "line-b" }, "key"), null);
  assert.equal(resolveSelectedRowId(null, "key"), null);
});

test("history tab requires history payload availability", () => {
  assert.equal(resolveDetailTab("history", false), "detail");
  assert.equal(resolveDetailTab("history", true), "history");
  assert.equal(resolveDetailTab("detail", true), "detail");
  assert.equal(resolveDetailTab("anything-else", true), "detail");
});

test("pivot swap changes summary key distribution", () => {
  const rows = [
    { bucket: "2024-01", result: "1-0" },
    { bucket: "2024-02", result: "0-1" },
    { bucket: "2024-03", result: "1-0" },
  ];

  const byBucket = summarizePivot(rows, "bucket");
  const byResult = summarizePivot(rows, "result");

  assert.equal(byBucket.length, 3);
  assert.equal(byResult[0].key, "1-0");
  assert.equal(byResult[0].count, 2);
});

test("pivot toggle swaps visible time-usage columns by pivot", () => {
  const rows = normalizeStatsRows({
    buckets: [
      { bucket: "Self", total_games: 10, total_moves: 120, avg_time_spent_seconds: 13.2, avg_time_spent_fraction: 0.08 },
    ],
  });
  const selfVsOppColumns = resolveColumns(rows, ["bucket", "total_games", "total_moves"]);
  const inBookColumns = resolveColumns(rows, ["bucket", "avg_time_spent_fraction", "avg_time_spent_seconds"]);

  assert.deepEqual(selfVsOppColumns, ["bucket", "total_games", "total_moves"]);
  assert.deepEqual(inBookColumns, ["bucket", "avg_time_spent_fraction", "avg_time_spent_seconds"]);
});

test("band-size change keeps rows consumable", () => {
  const rows100 = normalizeStatsRows({ buckets: [{ white_band: "1500-1599", total_games: 2 }] });
  const rows200 = normalizeStatsRows({ buckets: [{ white_band: "1400-1599", total_games: 3 }] });

  assert.equal(rows100[0].white_band, "1500-1599");
  assert.equal(rows200[0].white_band, "1400-1599");
});

test("band-size guardrails enforce min/max/step", () => {
  const guardrails = {
    min: 50,
    max: 400,
    step: 50,
    allowedBandSizes: [50, 100, 150, 200, 250, 300, 350, 400],
    fallback: 100,
  };

  assert.equal(normalizeBandSizeByGuardrails(25, guardrails), 100);
  assert.equal(normalizeBandSizeByGuardrails(450, guardrails), 100);
  assert.equal(normalizeBandSizeByGuardrails(125, guardrails), 100);
  assert.equal(normalizeBandSizeByGuardrails(150, guardrails), 150);
});

test("summary blocks update from metadata payload", () => {
  const summary = buildRatingBandSummary({
    band_size: 150,
    allowed_band_sizes: [50, 100, 150, 200],
    totals: { total_games: 42, bucket_count: 8 },
    percentiles: { p25_compliance_rate: 0.4, p50_compliance_rate: 0.55, p75_compliance_rate: 0.8 },
  });

  assert.equal(summary[0].value, "150");
  assert.equal(summary[1].value, "42");
  assert.equal(summary[2].value, "8");
  assert.equal(summary[3].value, "55.0%");
  assert.equal(summary[4].value, "80.0%");
});
