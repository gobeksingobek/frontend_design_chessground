function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function checkCreateSessionResponseShape(payload) {
  assert(isObject(payload), "create session response must be an object");
  assert(typeof payload.session_id === "string", "create session response.session_id must be string");
  assert(isObject(payload.item), "create session response.item must be an object");
  assert(typeof payload.item.branch_id === "string", "item.branch_id must be string");
  assert(typeof payload.item.fen === "string", "item.fen must be string");
  assert(typeof payload.item.prompt === "string", "item.prompt must be string");
  assert(typeof payload.item.expected_move_uci === "string", "item.expected_move_uci must be string");
  assert(["easy", "medium", "hard"].includes(payload.item.difficulty), "item.difficulty must be easy|medium|hard");
  assert(isObject(payload.queue_snapshot), "queue_snapshot must be object");
  for (const key of ["remaining", "learned", "needs_review"]) {
    assert(typeof payload.queue_snapshot[key] === "number", `queue_snapshot.${key} must be number`);
  }
}

function checkAnswerSessionResponseShape(payload) {
  assert(isObject(payload), "answer response must be object");
  assert(["correct", "incorrect"].includes(payload.outcome), "outcome must be correct|incorrect");
  assert(["again", "hard", "good", "easy"].includes(payload.grade), "grade must be valid");
  assert(typeof payload.streak_delta === "number", "streak_delta must be number");
  assert(["learned", "needs_review"].includes(payload.item_state), "item_state must be learned|needs_review");
  if (payload.next_item !== undefined && payload.next_item !== null) {
    assert(isObject(payload.next_item), "next_item must be object when provided");
    assert(typeof payload.next_item.branch_id === "string", "next_item.branch_id must be string");
    assert(typeof payload.next_item.expected_move_uci === "string", "next_item.expected_move_uci must be string");
  }
  if (payload.outcome === "incorrect") {
    assert(isObject(payload.remediation), "incorrect outcome must include remediation");
    assert(typeof payload.remediation.best_move_uci === "string", "remediation.best_move_uci must be string");
    assert(Array.isArray(payload.remediation.principal_variation), "remediation.principal_variation must be array");
    assert(payload.remediation.principal_variation.every((move) => typeof move === "string"), "remediation.principal_variation entries must be strings");
    assert(typeof payload.remediation.explanation_markdown === "string", "remediation.explanation_markdown must be string");
    assert(typeof payload.remediation.retry_required === "boolean", "remediation.retry_required must be boolean");
  }
}

checkCreateSessionResponseShape({
  session_id: "00000000-0000-0000-0000-000000000000",
  item: {
    branch_id: "line-1",
    fen: "fen-value",
    prompt: "Find the repertoire move",
    expected_move_uci: "e2e4",
    difficulty: "medium",
  },
  queue_snapshot: { remaining: 10, learned: 2, needs_review: 1 },
});

checkAnswerSessionResponseShape({
  outcome: "correct",
  grade: "good",
  streak_delta: 1,
  item_state: "learned",
  next_item: null,
});

checkAnswerSessionResponseShape({
  outcome: "incorrect",
  grade: "again",
  streak_delta: -1,
  item_state: "needs_review",
  remediation: {
    best_move_uci: "e2e4",
    principal_variation: ["e2e4", "e7e5"],
    explanation_markdown: "Try the mainline move.",
    retry_required: true,
  },
});

console.log("Trainer contract checks passed for /trainer/sessions endpoints.");
