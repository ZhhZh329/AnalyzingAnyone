window.APP_CONFIG = {
  API_BASE: 'http://127.0.0.1:8000',
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
