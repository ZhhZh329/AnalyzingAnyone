const I18N_DICT = {
  zh: {
    landing: {
      protocol: '版本 0.1',
      status: '处理中...',
      title: 'Analyzing\nAnyone\n重构认知的架构',
      blurb: '选取文本语料库，将该语料库转换为时间线和证据卡片，通过多个特定理论专家agent分析，生成人物调研报告',
      enter: '开始分析',
    },
    input: {
      title: '用户输入',
      desc: '输入名字并上传 ZIP 档案，系统将自动生成你的分析文档。',
      nameLabel: '名字',
      namePlaceholder: '请输入名字',
      dragTitle: '拖入档案（.zip）',
      dragHint: '或者从本地选择文件',
      selectZip: '选择 ZIP',
      loaded: '已加载：{name}',
      start: '开始生成分析文档',
      running: '分析运行中...',
      backAria: '返回主页',
    },
    overlay: {
      header: '过场状态',
      preparingTitle: '准备开始分析',
      preparingSub: '正在初始化分析协议栈...',
      ingestingSub: '正在接收并校验资料包...',
      dispatchSub: '正在派发后端工作流...',
      runningTitle: '分析流程进行中',
      currentStage: '当前阶段：{stage}',
      compileTitle: '正在整理文档',
      compileSub: '正在渲染最终报告...',
      readySub: '文档已生成。',
      step: '步骤',
    },
    report: {
      header: '最终文档',
      title: '{name} 的分析报告',
      defaultName: '该用户',
      generatedAt: '生成时间：{time}',
      restart: '重新分析',
    },
    status: {
      booting: '启动中',
      created: '已创建',
      queued: '排队中',
      ingesting: '归档处理中',
      processing: '处理中',
      running: '运行中',
      completed: '已完成',
      failed: '失败',
      partial_failed: '部分失败',
      cancelled: '已取消',
      pending: '待处理',
      success: '已完成',
    },
    stage: {
      create_project: '初始化用户档案',
      upload_package: '接收并校验资料包',
      input_normalize: '输入标准化',
      assemble: '证据汇编',
      discipline: '多学科并行分析',
      critique: '批判复核',
      synthesize: '综合归纳',
      report: '生成最终报告',
    },
    errors: {
      requestDefault: '请求失败',
      onlyZip: '后端仅支持 .zip 文件。',
      needName: '请输入你的名字。',
      needZip: '请上传 ZIP 文件。',
      reportNotReady: '报告暂未就绪，请稍后重试。',
      pollTimeout: '轮询超时，请稍后重试。',
      createProjectInvalid: '创建项目响应异常，请重试。',
      uploadInvalid: '上传资料包响应异常，请重试。',
      runInvalid: '创建分析任务响应异常，请重试。',
      runTerminated: '任务异常结束：{status}',
      failedRetry: '分析失败，请重试。',
      projectName: '{name} 的分析项目',
      projectDesc: '个人档案分析',
      requestPrefix: '请求失败（{code}）：{message}',
    },
  },
  en: {
    landing: {
      protocol: 'VERSION 0.1',
      status: 'ANALYZING ...',
      title: 'Analyzing\nAnyone',
      blurb: 'The project takes a corpus of publicly available texts about a person, converts that corpus into a timeline and evidence cards, runs multiple theory-specific lenses in parallel, critiques weak claims, synthesizes cross-lens patterns, and generates a final report.',
      enter: 'ENTER ANALYSIS',
    },
    input: {
      title: 'Input Subject',
      desc: 'Enter your name and upload a ZIP archive. The system will generate your analysis document automatically.',
      nameLabel: 'Your Name',
      namePlaceholder: 'Type your name',
      dragTitle: 'Drop Archive (.zip)',
      dragHint: 'or select from local files',
      selectZip: 'Select ZIP',
      loaded: 'Loaded: {name}',
      start: 'Generate Analysis Document',
      running: 'Analysis Running...',
      backAria: 'Back to main page',
    },
    overlay: {
      header: 'Transition Status',
      preparingTitle: 'Preparing Analysis',
      preparingSub: 'Initializing protocol stack...',
      ingestingSub: 'Receiving and validating archive package...',
      dispatchSub: 'Dispatching backend workflow...',
      runningTitle: 'Pipeline in Motion',
      currentStage: 'Current stage: {stage}',
      compileTitle: 'Compiling Document',
      compileSub: 'Rendering final report...',
      readySub: 'Document ready.',
      step: 'STEP',
    },
    report: {
      header: 'Final Document',
      title: '{name} Analysis Report',
      defaultName: 'Subject',
      generatedAt: 'Generated: {time}',
      restart: 'New Analysis',
    },
    status: {
      booting: 'Booting',
      created: 'Created',
      queued: 'Queued',
      ingesting: 'Ingesting',
      processing: 'Processing',
      running: 'Running',
      completed: 'Completed',
      failed: 'Failed',
      partial_failed: 'Partial Failed',
      cancelled: 'Cancelled',
      pending: 'Pending',
      success: 'Success',
    },
    stage: {
      create_project: 'Initialize Subject Profile',
      upload_package: 'Archive Intake',
      input_normalize: 'Input Normalize',
      assemble: 'Evidence Assembly',
      discipline: 'Parallel Lenses',
      critique: 'Critical Review',
      synthesize: 'Synthesis Pass',
      report: 'Final Report',
    },
    errors: {
      requestDefault: 'Request failed',
      onlyZip: 'Only .zip files are supported by the backend.',
      needName: 'Please enter your name.',
      needZip: 'Please upload a ZIP file.',
      reportNotReady: 'Report is not ready yet. Please retry shortly.',
      pollTimeout: 'Polling timed out. Please retry later.',
      createProjectInvalid: 'Invalid response while creating project. Please retry.',
      uploadInvalid: 'Invalid response while uploading package. Please retry.',
      runInvalid: 'Invalid response while creating run. Please retry.',
      runTerminated: 'Run terminated unexpectedly: {status}',
      failedRetry: 'Analysis failed. Please retry.',
      projectName: '{name} Analysis Project',
      projectDesc: 'Personal archive analysis',
      requestPrefix: 'Request failed ({code}): {message}',
    },
  },
};

function getNested(obj, path) {
  return path.split('.').reduce((acc, key) => (acc && acc[key] !== undefined ? acc[key] : undefined), obj);
}

function applyVars(template, vars) {
  return String(template).replace(/\{(\w+)\}/g, (_, key) => (vars[key] !== undefined ? vars[key] : `{${key}}`));
}

function t(lang, key, vars = {}) {
  const langPack = I18N_DICT[lang] || I18N_DICT.zh;
  const found = getNested(langPack, key);
  if (found === undefined) return key;
  if (typeof found === 'string') return applyVars(found, vars);
  return found;
}

function statusLabel(lang, status) {
  const text = t(lang, `status.${status}`);
  return text === `status.${status}` ? status : text;
}

function stageLabel(lang, stageKey) {
  const text = t(lang, `stage.${stageKey}`);
  return text === `stage.${stageKey}` ? stageKey : text;
}

function getPipeline(lang) {
  return window.APP_CONFIG.PIPELINE_KEYS.map((key) => ({ key, label: stageLabel(lang, key) }));
}

window.i18n = {
  dict: I18N_DICT,
  t,
  statusLabel,
  stageLabel,
  getPipeline,
};
