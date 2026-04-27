(function () {
  function InputPage({ t, name, setName, zipFile, setZipFile, dragging, setDragging, onBack, onStart, loading, error }) {
    return (
      <main className="screen-enter relative min-h-screen bg-canvas px-6 py-8 md:px-12 md:py-10">
        <button className="back-arrow btn-fx" onClick={onBack} aria-label={t('input.backAria')} title={t('input.backAria')}>
          <span>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M15 5L8 12L15 19" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
        </button>

        <section className="mx-auto mt-8 w-full max-w-4xl border hairline border-ink/35 bg-white/20 p-6 md:p-8">
          <h2 className="font-serif text-3xl text-ink md:text-4xl">{t('input.title')}</h2>
          <p className="mt-3 text-base leading-7 text-ink/80">{t('input.desc')}</p>

          <label className="mt-8 block">
            <span className="mono-meta text-ink/70">{t('input.nameLabel')}</span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t('input.namePlaceholder')}
              className="mt-2 w-full border hairline border-ink/45 bg-transparent px-3 py-3 text-lg outline-none focus:border-ink"
            />
          </label>

          <div
            className={`${dragging ? 'border-ink bg-white/40' : ''} mt-6 dashline border-ink/45 p-9 text-center transition-colors`}
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragging(false);
              const file = e.dataTransfer.files?.[0];
              if (file) setZipFile(file);
            }}
          >
            <p className="text-2xl">{t('input.dragTitle')}</p>
            <p className="mt-2 text-sm text-ink/70">{t('input.dragHint')}</p>

            <label className="mt-4 inline-block cursor-pointer border hairline border-ink/50 px-4 py-2 mono-meta btn-fx hover:border-ink">
              <span>{t('input.selectZip')}</span>
              <input
                type="file"
                accept=".zip"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) setZipFile(file);
                }}
              />
            </label>

            {zipFile ? <p className="mt-4 mono-meta text-sage">{t('input.loaded', { name: zipFile.name })}</p> : null}
          </div>

          {error ? <p className="mt-5 border-l-2 border-terra pl-3 text-sm text-terra">{error}</p> : null}

          <button
            onClick={onStart}
            disabled={loading}
            className="mt-7 w-full border hairline border-ink bg-ink px-5 py-3 mono-meta text-canvas btn-fx btn-fx-light disabled:cursor-not-allowed disabled:opacity-50"
          >
            <span>{loading ? t('input.running') : t('input.start')}</span>
          </button>
        </section>
      </main>
    );
  }

  window.InputPage = InputPage;
})();
