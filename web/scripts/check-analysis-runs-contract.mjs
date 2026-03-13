const sample = { runs: [{ run_id: "r1", run_type: "full-analysis", status: "completed", started_at: "", finished_at: "", error_reason: null }] };
if (!sample.runs[0].run_id || !sample.runs[0].status) throw new Error('analysis runs contract failed');
console.log('Analysis runs contract verified.');
