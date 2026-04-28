// detection-panel.jsx — Boczny panel z listą wykrytych danych + filtry kategorii

const { useMemo: useMemoDP } = React;

function DetectionPanel({ spans, hiddenLabels, toggleLabel, unmaskedPlaceholders, togglePlaceholder, hoveredId, setHoveredId, theme }) {
  // Grupuj per label
  const grouped = useMemoDP(() => {
    const m = new Map();
    for (const s of spans) {
      const arr = m.get(s.label) || [];
      arr.push(s);
      m.set(s.label, arr);
    }
    return [...m.entries()].sort((a, b) => b[1].length - a[1].length);
  }, [spans]);

  const total = spans.length;
  const hasUnmaskFn = typeof togglePlaceholder === "function";
  const unmaskedSet = unmaskedPlaceholders || new Set();

  return (
    <aside className="detect-panel">
      <header className="detect-head">
        <div className="detect-title">
          <h3>Wykryte dane</h3>
          <span className="detect-count" data-zero={total === 0}>{String(total).padStart(2, "0")}</span>
        </div>
        <p className="detect-sub">
          {total === 0
            ? "Po analizie zobaczysz tu listę wykrytych danych pogrupowaną wg kategorii."
            : "Kropka po prawej: kategorię (przy nagłówku) lub konkretne wystąpienie (przy linii)."}
        </p>
      </header>

      <div className="detect-body">
        {grouped.map(([label, items]) => {
          const c = chipColor(label, theme);
          const meta = window.LABEL_META[label] || { icon: "·", desc: label };
          const isHidden = hiddenLabels.has(label);
          return (
            <div key={label} className={`detect-group ${isHidden ? "is-hidden" : ""}`}>
              <button className="detect-group-head" onClick={() => toggleLabel(label)}>
                <span className="detect-icon" style={{ background: c.bg, color: c.fg, borderColor: c.border }}>
                  {meta.icon}
                </span>
                <div className="detect-group-meta">
                  <div className="detect-group-name">
                    <span>{label}</span>
                    <span className="detect-group-num">{items.length}</span>
                  </div>
                  <small>{meta.desc}</small>
                </div>
                <span className="detect-toggle" aria-label={isHidden ? "Pokaż" : "Ukryj"}>
                  {isHidden ? "○" : "●"}
                </span>
              </button>
              <ul className="detect-list">
                {items.map((s, i) => {
                  const id = `${s.start}-${s.end}`;
                  const isH = hoveredId === id;
                  const isUnmasked = unmaskedSet.has(s.placeholder);
                  return (
                    <li
                      key={i}
                      className={`detect-item ${isH ? "is-hover" : ""} ${isUnmasked ? "is-unmasked" : ""}`}
                      onMouseEnter={() => setHoveredId(id)}
                      onMouseLeave={() => setHoveredId(null)}
                    >
                      <code className="detect-orig">{s.text}</code>
                      <span className="detect-arrow">→</span>
                      <code className="detect-place" style={{ color: c.fg }}>{s.placeholder}</code>
                      <span className={`detect-source detect-source-${s.source}`} title={s.source === "regex" ? "wykryte regex'em (deterministyczne)" : "wykryte modelem AI"}>
                        {s.source === "regex" ? "regex" : "AI"}
                      </span>
                      {hasUnmaskFn && (
                        <button
                          className={`detect-item-toggle ${isUnmasked ? "is-off" : ""}`}
                          onClick={(e) => { e.stopPropagation(); togglePlaceholder(s.placeholder); }}
                          aria-label={isUnmasked ? `Maskuj ${s.placeholder}` : `Pokaż oryginał ${s.placeholder}`}
                          title={isUnmasked ? `Włącz maskowanie ${s.placeholder}` : `Pokaż oryginał (${s.placeholder} bez maski)`}
                        >
                          {isUnmasked ? "○" : "●"}
                        </button>
                      )}
                    </li>
                  );
                })}
              </ul>
            </div>
          );
        })}

        {total === 0 && (
          <div className="detect-empty">
            <div className="detect-empty-glyph">·</div>
            <p>Tutaj pokażą się wykryte dane.</p>
          </div>
        )}
      </div>
    </aside>
  );
}

window.DetectionPanel = DetectionPanel;
