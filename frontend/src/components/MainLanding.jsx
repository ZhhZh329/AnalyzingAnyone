(function () {
  function MainLanding({ t, onEnter }) {
    const titleLines = t('landing.title').split('\n');

    return (
      <main className="screen-enter relative min-h-screen overflow-hidden bg-canvas px-6 pb-6 pt-6 md:px-14 md:pb-8 md:pt-8">
        <window.HelixBackground />

        <header className="relative z-10 flex items-center text-[11px] md:text-[13px]">
          <p className="mono-meta">{t('landing.protocol')}</p>
          <p className="mono-meta absolute left-1/2 -translate-x-1/2 text-center">{t('landing.status')}</p>
        </header>

        <section className="relative z-10 mt-6 grid max-w-5xl gap-6 md:mt-12 md:gap-8">
          <h1 className="poster-title max-w-[700px] text-ink">
            {titleLines.map((line, idx) => (
              <span key={`${line}_${idx}`}>
                {line}
                {idx !== titleLines.length - 1 ? <br /> : null}
              </span>
            ))}
          </h1>

          <p className="max-w-[560px] text-[16px] leading-[1.45] md:text-[24px] md:leading-[1.3]">{t('landing.blurb')}</p>
        </section>

        <footer className="pointer-events-none fixed bottom-5 right-5 z-20 md:bottom-8 md:right-10">
          <button className="access-button pointer-events-auto" onClick={onEnter}>
            {t('landing.enter')}
          </button>
        </footer>
      </main>
    );
  }

  window.MainLanding = MainLanding;
})();
