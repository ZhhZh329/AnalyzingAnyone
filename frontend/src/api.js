function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function request(path, options = {}) {
  const base = (window.APP_CONFIG.API_BASE || '').replace(/\/$/, '');
  const url = `${base}${path}`;
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
    const message =
      payload?.error?.message ||
      payload?.message ||
      text ||
      response.statusText ||
      'Request failed';
    const err = new Error(message);
    err.code = code;
    err.rawMessage = message;
    throw err;
  }

  return payload;
}

export async function getAnalysisTiers() {
  // request 默认 method 是 GET，直接传 path 即可
  return request('/analysis-tiers');
}

// 修改/新增：创建分析任务（带上配置）
export async function createAnalysisRun(projectId, payload) {
  // 指定 POST 方法，并将包含 analysis_tier 的数据传入 body
  return request(`/projects/${projectId}/runs`, {
    method: 'POST',
    body: payload
  });
}
window.api = {
  sleep,
  request,
};
