(function () {
  // 提取 useState 和 useEffect，假设 React 已挂载在全局
  const { useState, useEffect } = React;

  function InputPage({ t, name, setName, zipFile, setZipFile, dragging, setDragging, onBack, onStart, loading, error }) {
    // 1. 新增：档位数据源与当前选中项的状态
    const [tiersData, setTiersData] = useState({ tiers: [], default_tier: 'lite' });
    const [selectedTier, setSelectedTier] = useState('lite');

    // 2. 新增：组件挂载时请求档位接口
    useEffect(() => {
      if (window.api && window.api.getAnalysisTiers) {
        window.api.getAnalysisTiers()
          .then((data) => {
            if (data && data.tiers) {
              setTiersData(data);
              setSelectedTier(data.default_tier);
            }
          })
          .catch((err) => console.error('Failed to load analysis tiers', err));
      }
    }, []);

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

          {/* ================= 新增：档位选择器 UI ================= */}
          {tiersData.tiers.length > 0 && (
            <div className="mt-8">
              <span className="mono-meta text-ink/70">Analysis Tier (分析档位)</span>
              <div className="mt-3 grid grid-cols-1 gap-4 md:grid-cols-3">
                {tiersData.tiers.map((tier) => (
                  <label
                    key={tier.key}
                    className={`block cursor-pointer border hairline p-4 transition-colors ${
                      selectedTier === tier.key ? 'border-ink bg-ink/5' : 'border-ink/30 hover:border-ink/60'
                    }`}
                  >
                    <input
                      type="radio"
                      name="analysis_tier"
                      value={tier.key}
                      checked={selectedTier === tier.key}
                      onChange={() => setSelectedTier(tier.key)}
                      className="hidden"
                    />
                    <div className="font-serif text-lg text-ink">{tier.label}</div>
                    <div className="mt-1 text-sm text-ink/80">{tier.description}</div>
                    <div className="mt-4 text-xs mono-meta text-ink/60">
                      Lenses: {tier.estimated_lens_count} | ~{tier.estimated_duration_minutes} min
                    </div>
                  </label>
                ))}
              </div>
            </div>
          )}
          {/* ======================================================== */}

          {error ? <p className="mt-5 border-l-2 border-terra pl-3 text-sm text-terra">{error}</p> : null}

          {/* 3. 修改：点击开始时，将 selectedTier 传递给父组件的 onStart */}
          <button
            onClick={() => onStart(selectedTier)}
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