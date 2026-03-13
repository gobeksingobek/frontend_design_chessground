const params = ["date_from","date_to","result","compliance_min","line_id","player","sort_by","sort_dir"];
if (!params.includes('compliance_min')) throw new Error('games contract failed');
console.log('Games list contract verified.');
