const DEFAULT_API_BASE = (() => {
  if (window.location.protocol === 'http:' || window.location.protocol === 'https:') {
    return window.location.origin;
  }
  return 'http://127.0.0.1:8000';
})();

window.APP_CONFIG = {
  API_BASE: DEFAULT_API_BASE,
  TERMINAL_STATUSES: new Set(['completed', 'failed', 'partial_failed', 'cancelled']),
  PIPELINE_KEYS: [
    'create_project',
    'upload_package',
    'input_normalize',
    'assemble',
    'discipline',
    'critique',
    'synthesize',
    'report',
  ],
};
