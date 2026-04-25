function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function request(path, options = {}) {
  const url = `${window.APP_CONFIG.API_BASE}${path}`;
  const init = {
    method: options.method || 'GET',
    headers: {
      Accept: 'application/json',
      ...(options.headers || {}),
    },
  };

  if (options.formData) {
    init.body = options.formData;
  } else if (options.body !== undefined) {
    init.headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(options.body);
  }

  const response = await fetch(url, init);
  const text = await response.text();
  let payload = null;

  try {
    payload = text ? JSON.parse(text) : null;
  } catch (_) {
    payload = null;
  }

  if (!response.ok || payload?.success === false) {
    const code = payload?.error?.code || `HTTP_${response.status}`;
    const message = payload?.error?.message || payload?.message || response.statusText || 'Request failed';
    const err = new Error(message);
    err.code = code;
    err.rawMessage = message;
    throw err;
  }

  return payload;
}

window.api = {
  sleep,
  request,
};
