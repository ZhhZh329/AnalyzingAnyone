(function () {
  function TransitionOverlay({ visible, t, toStatusLabel, pipeline, title, subtitle, runStatus, stageState }) {
    if (!visible) return null;

    return (
      <div className="transition-overlay">
        <window.HelixBackground dense={true} />

        <div className="relative z-20 mr-auto ml-3 flex min-h-screen w-full max-w-5xl flex-col px-5 py-8 md:ml-10 md:px-8 md:py-10 lg:ml-16">
          <header className="flex items-center justify-between border-b hairline border-ink/30 pb-4">
            <p className="mono-meta">{t('overlay.header')}</p>
            <div className="flex items-center gap-2">
              <span className="status-pulse"></span>
              <p className="mono-meta">{toStatusLabel(runStatus || 'processing')}</p>
            </div>
          </header>

          <section className="mt-8 max-w-3xl">
            <h2 className="font-serif text-5xl leading-[1.05] text-ink md:text-6xl">{title}</h2>
            <p className="mt-3 text-lg leading-8 text-ink/80 md:text-xl">{subtitle}</p>
          </section>

          <section className="mt-9 grid gap-3 md:grid-cols-2">
            {pipeline.map((stage, index) => {
              const status = stageState[stage.key] || 'pending';
              const done = status === 'success';
              const running = status === 'running';
              const failed = status === 'failed' || status === 'partial_failed';

              return (
                <article
                  key={stage.key}
                  className={[
                    'border hairline p-3',
                    done ? 'border-sage bg-sage/10' : '',
                    running ? 'border-ink bg-white/45' : '',
                    failed ? 'border-terra bg-terra/10' : '',
                    !done && !running && !failed ? 'border-ink/30 bg-white/20' : '',
                  ].join(' ')}
                >
                  <p className="mono-meta text-ink/70">
                    {t('overlay.step')} {String(index + 1).padStart(2, '0')}
                  </p>
                  <p className="mt-2 text-base md:text-lg">{stage.label}</p>
                  <p className="mt-2 mono-meta text-ink/65">{toStatusLabel(status)}</p>
                </article>
              );
            })}
          </section>
        </div>
      </div>
    );
  }

  window.TransitionOverlay = TransitionOverlay;
})();
