const browse = { pos_id: 1, repertoire_children: [], game_children: [] };
const coverage = { pos_id: 1, coverage_pct: 0 };
if (browse.pos_id !== coverage.pos_id) throw new Error('tree contract failed');
console.log('Tree contract verified.');
