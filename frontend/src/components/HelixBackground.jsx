(function () {
  const { useMemo } = React;

  function HelixBackground({ dense = false }) {
    const rows = useMemo(() => {
      const symbols = ['A', 'T', 'C', 'G'];
      const count = dense ? 64 : 54;

      return Array.from({ length: count }, (_, i) => {
        const t = i * 0.28;
        const wave = Math.sin(t);
        const wave2 = Math.sin(t + 1.2);
        const leftX = 88 + wave * 48;
        const rightX = 318 - wave * 48;
        const tilt = wave2 * 7;
        const opacity = 0.24 + Math.abs(wave) * 0.7;

        return {
          id: i,
          top: 14 + i * 14,
          leftX,
          rightX,
          tilt,
          opacity,
          leftChar: symbols[i % 4],
          rightChar: symbols[(i + 1) % 4],
          delay: `${(i % 14) * -0.23}s`,
        };
      });
    }, [dense]);

    return (
      <div className="helix-canvas" aria-hidden="true">
        <div className="helix-column" style={{ left: '68%' }}>
          {rows.map((row) => {
            const lineLength = row.rightX - row.leftX;
            return (
              <div key={row.id} className="helix-row" style={{ top: `${row.top}px`, animationDelay: row.delay }}>
                <span
                  className="helix-line"
                  style={{
                    left: `${row.leftX}px`,
                    width: `${lineLength}px`,
                    transform: `translateY(-50%) rotate(${row.tilt}deg)`,
                    opacity: 0.62,
                    background: '#CBD9F4',
                  }}
                ></span>

                <span
                  className="helix-base"
                  style={{ left: `${row.leftX}px`, opacity: row.opacity, color: '#355C9A', fontSize: '15px' }}
                >
                  {row.leftChar}
                </span>
                <span
                  className="helix-base"
                  style={{ left: `${row.rightX}px`, opacity: row.opacity * 0.66, color: '#86A6DA', fontSize: '15px' }}
                >
                  {row.rightChar}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  window.HelixBackground = HelixBackground;
})();
