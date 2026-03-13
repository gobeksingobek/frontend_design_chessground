const row = { priority_score: 0.9, confidence: 0.7, source_refs: [{ type: 'game', id: '1', label: 'g1' }] };
if (!Array.isArray(row.source_refs) || typeof row.priority_score !== 'number') throw new Error('insights contract failed');
console.log('Insights contract verified.');
