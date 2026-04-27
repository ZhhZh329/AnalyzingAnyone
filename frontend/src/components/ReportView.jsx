(function () {
  function ReportView({ t, name, report, generatedAt, onRestart }) {
    const titleName = name || t('report.defaultName');

    return (
      <main className="screen-enter min-h-screen bg-canvas px-6 py-8 md:px-12 md:py-10">
        <header className="mx-auto flex w-full max-w-5xl items-center justify-between border-b hairline border-ink/25 pb-4">
          <div>
            <p className="mono-meta">{t('report.header')}</p>
            <h1 className="mt-2 font-serif text-3xl md:text-4xl">{t('report.title', { name: titleName })}</h1>
          </div>
          <button onClick={onRestart} className="mono-meta border hairline border-ink px-3 py-1.5 btn-fx hover:bg-ink hover:text-canvas">
            <span>{t('report.restart')}</span>
          </button>
        </header>

        <section className="mx-auto mt-7 w-full max-w-5xl border hairline border-ink/35 bg-white/35 p-6 md:p-8">
          {generatedAt ? <p className="mono-meta text-ink/60">{t('report.generatedAt', { time: new Date(generatedAt).toLocaleString() })}</p> : null}
          <article className="report-body mt-5 border hairline border-ink/30 bg-white/85 p-5 font-serif text-[16px] leading-7 text-ink md:p-7">{report}</article>
        </section>
      </main>
    );
  }

  window.ReportView = ReportView;
})();
