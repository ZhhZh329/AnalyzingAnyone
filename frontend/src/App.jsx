(function () {
  const { useMemo, useState } = React;

  function App() {
    const [lang, setLang] = useState('zh');
    const [screen, setScreen] = useState('main');
    const [name, setName] = useState('');
    const [zipFile, setZipFileState] = useState(null);
    const [dragging, setDragging] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    const [report, setReport] = useState('');
    const [generatedAt, setGeneratedAt] = useState('');

    const [transition, setTransition] = useState({
      visible: false,
      title: '',
      subtitle: '',
      runStatus: 'queued',
      stageState: {},
    });

    const t = (key, vars = {}) => window.i18n.t(lang, key, vars);
    const toStatusLabel = (status) => window.i18n.statusLabel(lang, status);

    const pipeline = useMemo(() => window.i18n.getPipeline(lang), [lang]);

    function toRequestError(err) {
      const code = err?.code || 'UNKNOWN';
      const rawMessage = err?.rawMessage || err?.message || t('errors.requestDefault');
      return t('errors.requestPrefix', { code, message: rawMessage });
    }

    function setZipFile(file) {
      if (!file) return;
      if (!file.name.toLowerCase().endsWith('.zip')) {
        setError(t('errors.onlyZip'));
        return;
      }
      setError('');
      setZipFileState(file);
    }

    function mergeStageState(patch) {
      setTransition((prev) => ({
        ...prev,
        stageState: {
          ...prev.stageState,
          ...patch,
        },
      }));
    }

    function syncRunStages(runDetail) {
      const stages = runDetail?.stages || [];
      const patch = {};
      for (const item of stages) {
        patch[item.stage_key] = item.status;
      }
      mergeStageState(patch);
    }

    async function fetchReportWithRetry(projectId, runId) {
      for (let i = 0; i < 40; i += 1) {
        try {
          const reportRes = await window.api.request(`/projects/${projectId}/runs/${runId}/report`);
          return reportRes?.data || null;
        } catch (err) {
          if (String(err.code || err.message || '').includes('RUN_OUTPUT_NOT_READY')) {
            await window.api.sleep(1500);
            continue;
          }
          throw err;
        }
      }
      throw new Error(t('errors.reportNotReady'));
    }

    async function pollRun(projectId, runId) {
      for (let i = 0; i < 300; i += 1) {
        const runRes = await window.api.request(`/projects/${projectId}/runs/${runId}`);
        const detail = runRes?.data || null;
        const currentStatus = detail?.run?.status || 'running';
        const currentStage = detail?.run?.current_stage || 'assemble';
        const currentStageLabel = window.i18n.stageLabel(lang, currentStage);

        syncRunStages(detail);
        setTransition((prev) => ({
          ...prev,
          runStatus: currentStatus,
          title: t('overlay.runningTitle'),
          subtitle: t('overlay.currentStage', { stage: currentStageLabel }),
        }));

        if (window.APP_CONFIG.TERMINAL_STATUSES.has(currentStatus)) {
          return detail;
        }

        await window.api.sleep(2000);
      }

      throw new Error(t('errors.pollTimeout'));
    }

    function openTransition() {
      setTransition({
        visible: true,
        title: t('overlay.preparingTitle'),
        subtitle: t('overlay.preparingSub'),
        runStatus: 'booting',
        stageState: {},
      });
    }

    async function startAnalysis() {
      if (!name.trim()) {
        setError(t('errors.needName'));
        return;
      }
      if (!zipFile) {
        setError(t('errors.needZip'));
        return;
      }

      setError('');
      setLoading(true);
      setReport('');
      setGeneratedAt('');
      openTransition();

      try {
        mergeStageState({ create_project: 'running' });

        const projectRes = await window.api.request('/projects', {
          method: 'POST',
          body: {
            name: t('errors.projectName', { name: name.trim() }),
            description: t('errors.projectDesc'),
            subject: {
              display_name: name.trim(),
              aliases: [],
            },
          },
        });

        const projectId = projectRes?.data?.project_id;
        const subjectId = projectRes?.data?.subject_id;
        if (!projectId || !subjectId) {
          throw new Error(t('errors.createProjectInvalid'));
        }

        mergeStageState({ create_project: 'success', upload_package: 'running' });
        setTransition((prev) => ({
          ...prev,
          subtitle: t('overlay.ingestingSub'),
          runStatus: 'ingesting',
        }));

        const formData = new FormData();
        formData.append('subject_id', subjectId);
        formData.append('package_file', zipFile);
        formData.append('package_name', zipFile.name);
        formData.append('package_type', 'zip');

        const packageRes = await window.api.request(`/projects/${projectId}/ingestion-packages`, {
          method: 'POST',
          formData,
        });

        const packageId = packageRes?.data?.package_id;
        if (!packageId) {
          throw new Error(t('errors.uploadInvalid'));
        }

        mergeStageState({ upload_package: 'success' });
        setTransition((prev) => ({
          ...prev,
          subtitle: t('overlay.dispatchSub'),
          runStatus: 'queued',
        }));

        const runRes = await window.api.request(`/projects/${projectId}/runs`, {
          method: 'POST',
          body: {
            subject_id: subjectId,
            package_id: packageId,
            run_config: {
              schema_version: 'v0.1',
              model_profile: 'default',
            },
          },
        });

        const runId = runRes?.data?.run_id;
        if (!runId) {
          throw new Error(t('errors.runInvalid'));
        }

        const finalDetail = await pollRun(projectId, runId);
        const finalStatus = finalDetail?.run?.status || 'failed';
        if (finalStatus !== 'completed' && finalStatus !== 'partial_failed') {
          const backendMessage = finalDetail?.error?.message;
          throw new Error(backendMessage || t('errors.runTerminated', { status: toStatusLabel(finalStatus) }));
        }

        setTransition((prev) => ({
          ...prev,
          title: t('overlay.compileTitle'),
          subtitle: t('overlay.compileSub'),
          runStatus: finalStatus,
        }));

        const reportData = await fetchReportWithRetry(projectId, runId);
        setReport(reportData?.content || '');
        setGeneratedAt(reportData?.generated_at || '');

        setTransition((prev) => ({
          ...prev,
          runStatus: 'completed',
          subtitle: t('overlay.readySub'),
          stageState: {
            ...prev.stageState,
            report: 'success',
          },
        }));

        await window.api.sleep(450);
        setTransition((prev) => ({ ...prev, visible: false }));
        setScreen('report');
      } catch (err) {
        setTransition((prev) => ({ ...prev, visible: false }));
        const fallback = t('errors.failedRetry');
        const message = err?.code ? toRequestError(err) : (err?.message || fallback);
        setError(message);
      } finally {
        setLoading(false);
      }
    }

    function resetAll() {
      setScreen('main');
      setName('');
      setZipFileState(null);
      setDragging(false);
      setLoading(false);
      setError('');
      setReport('');
      setGeneratedAt('');
      setTransition({
        visible: false,
        title: '',
        subtitle: '',
        runStatus: 'queued',
        stageState: {},
      });
    }

    return (
      <>
        <div className={`lang-switch mono-meta ${screen === 'main' ? 'on-main' : ''}`} role="group" aria-label="language switch">
          <button className={lang === 'zh' ? 'active' : ''} onClick={() => setLang('zh')}>
            中
          </button>
          <button className={lang === 'en' ? 'active' : ''} onClick={() => setLang('en')}>
            EN
          </button>
        </div>

        {screen === 'main' ? <window.MainLanding t={t} onEnter={() => setScreen('input')} /> : null}

        {screen === 'input' ? (
          <window.InputPage
            t={t}
            name={name}
            setName={setName}
            zipFile={zipFile}
            setZipFile={setZipFile}
            dragging={dragging}
            setDragging={setDragging}
            onBack={() => setScreen('main')}
            onStart={startAnalysis}
            loading={loading}
            error={error}
          />
        ) : null}

        {screen === 'report' ? (
          <window.ReportView
            t={t}
            name={name}
            report={report}
            generatedAt={generatedAt}
            onRestart={resetAll}
          />
        ) : null}

        <window.TransitionOverlay
          visible={transition.visible}
          t={t}
          toStatusLabel={toStatusLabel}
          pipeline={pipeline}
          title={transition.title}
          subtitle={transition.subtitle}
          runStatus={transition.runStatus}
          stageState={transition.stageState}
        />
      </>
    );
  }

  window.App = App;
})();
