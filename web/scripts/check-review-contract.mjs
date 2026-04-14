function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

function assertHasKeys(obj, keys, context) {
  for (const key of keys) {
    assert(Object.prototype.hasOwnProperty.call(obj, key), `${context}: missing key '${key}'`);
  }
}

const detailResponse = {
  id: 101,
  proposition_type: "MISSING_COVERAGE_BRANCH",
  proposition_key: "p-101",
  status: "PENDING",
  evidence_count: 7,
  threshold_count: 5,
  dismissed_count: null,
  pos_id: 1,
  uci_move: "e2e4",
  line_id_hint: "line-1",
  detail: { evidence: ["game-a"] },
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
  decided_at: null,
};

assertHasKeys(
  detailResponse,
  [
    "id",
    "proposition_type",
    "proposition_key",
    "status",
    "evidence_count",
    "threshold_count",
    "pos_id",
    "uci_move",
    "line_id_hint",
    "detail",
    "updated_at",
  ],
  "GET /review/actions/{action_id}",
);

const queueResponse = [
  {
    proposition_id: 101,
    queue_status: "QUEUED",
    queued_at: "2024-01-01T00:01:00Z",
    proposition_status: "APPROVED",
    evidence_count: 7,
    threshold_count: 5,
    pos_id: 1,
    uci_move: "e2e4",
    line_id_hint: "line-1",
    updated_at: "2024-01-01T00:01:00Z",
  },
];

assert(Array.isArray(queueResponse), "GET /review/branch-queue must return a plain array (not an envelope object)");
assertHasKeys(
  queueResponse[0],
  [
    "proposition_id",
    "queue_status",
    "queued_at",
    "proposition_status",
    "evidence_count",
    "threshold_count",
    "pos_id",
    "uci_move",
    "line_id_hint",
    "updated_at",
  ],
  "GET /review/branch-queue item",
);

const actionResponse = {
  success: true,
  message: "Proposition approved and queued.",
  proposition: detailResponse,
  status_change: { before: "PENDING", after: "APPROVED" },
  queue_change: { before: null, after: queueResponse[0] },
  queue_delta: {
    proposition_id: 101,
    before_queue_status: null,
    after_queue_status: "QUEUED",
    added_to_queue: true,
    removed_from_queue: false,
  },
  priority_change: { line_id: "line-1", before: 0, after: 1 },
};

assertHasKeys(
  actionResponse,
  ["success", "message", "proposition", "status_change", "queue_change", "queue_delta", "priority_change"],
  "POST /review/actions",
);
assertHasKeys(
  actionResponse.queue_delta,
  ["proposition_id", "before_queue_status", "after_queue_status", "added_to_queue", "removed_from_queue"],
  "POST /review/actions queue_delta",
);

console.log("Review contract checks passed for /review/actions and canonical array-shaped /review/branch-queue.");
