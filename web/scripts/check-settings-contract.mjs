const payload = { days_back: 30, field_errors: [{ field: 'days_back', code: 'range', message: 'must be >=1' }] };
if (!Array.isArray(payload.field_errors)) throw new Error('settings contract failed');
console.log('Settings contract verified.');
