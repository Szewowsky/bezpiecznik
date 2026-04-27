// editor.jsx — TextEditor (input panel) + RedactedView (output) + DetectionPanel
// Korzysta z: window.SAMPLES, window.LABEL_META, window.locateSpans

const { useState, useMemo, useRef, useEffect } = React;

// ── Wspólne helpery ─────────────────────────────────────────────────────────
function buildSegments(text, spans) {
  const segs = [];
  let cursor = 0;
  for (const s of spans) {
    if (s.start > cursor) segs.push({ kind: "text", text: text.slice(cursor, s.start) });
    segs.push({ kind: "span", text: text.slice(s.start, s.end), span: s });
    cursor = s.end;
  }
  if (cursor < text.length) segs.push({ kind: "text", text: text.slice(cursor) });
  return segs;
}

function chipColor(label, theme = "dark") {
  const meta = window.LABEL_META[label];
  if (!meta) return { bg: "rgba(150,150,150,0.18)", fg: "#999", border: "rgba(150,150,150,0.4)" };
  const { hue } = meta;
  if (theme === "light") {
    return {
      bg:     `oklch(0.94 0.04 ${hue})`,
      fg:     `oklch(0.32 0.12 ${hue})`,
      border: `oklch(0.85 0.07 ${hue})`,
    };
  }
  return {
    bg:     `oklch(0.28 0.06 ${hue} / 0.55)`,
    fg:     `oklch(0.86 0.10 ${hue})`,
    border: `oklch(0.45 0.10 ${hue} / 0.6)`,
  };
}

// ── InputPanel ──────────────────────────────────────────────────────────────
function InputPanel({ text, onChange, onSampleLoad, onRedact, isLoading, hasRedaction, theme }) {
  const charCount = text.length;
  const wordCount = text.trim() ? text.trim().split(/\s+/).length : 0;
  const fileInputRef = useRef(null);

  function handleFile(e) {
    const f = e.target.files?.[0];
    if (!f) return;
    const r = new FileReader();
    r.onload = () => onChange(String(r.result || ""));
    r.readAsText(f);
  }

  return (
    <section className="panel input-panel">
      <header className="panel-head">
        <div className="panel-title">
          <span className="dot dot-input" />
          <h2>Twój tekst</h2>
          <span className="panel-sub">wklej, przeciągnij plik, albo wybierz przykład</span>
        </div>
        <div className="panel-actions">
          <button className="btn-ghost" onClick={() => fileInputRef.current?.click()}>
            <span className="ico">↥</span> Wczytaj plik
          </button>
          <input ref={fileInputRef} type="file" accept=".txt,.md" onChange={handleFile} hidden />
        </div>
      </header>

      <div className="sample-row">
        <span className="sample-label">START:</span>
        {Object.entries(window.SAMPLES).map(([k, s]) => (
          <button key={k} className="sample-pill" onClick={() => onSampleLoad(k)}>
            {s.title}
          </button>
        ))}
      </div>

      <div className="textarea-wrap">
        <textarea
          className="textarea"
          value={text}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Wklej tutaj fragment maila, transkryptu, notatki głosowej… &#10;&#10;Wszystko zostaje na Twoim komputerze. Tekst nigdy nie opuszcza tej aplikacji."
          spellCheck={false}
        />
        {!text && (
          <div className="textarea-hint">
            <kbd>⌘V</kbd> żeby wkleić · obsługa <code>.txt</code> i <code>.md</code>
          </div>
        )}
      </div>

      <footer className="panel-foot">
        <div className="meta">
          <span><b>{charCount.toLocaleString("pl-PL")}</b> znaków</span>
          <span className="sep">·</span>
          <span><b>{wordCount.toLocaleString("pl-PL")}</b> słów</span>
        </div>
        <div className="foot-actions">
          {text && (
            <button className="btn-ghost" onClick={() => onChange("")}>Wyczyść</button>
          )}
          <button
            className="btn-primary"
            onClick={onRedact}
            disabled={!text.trim() || isLoading}
          >
            {isLoading ? (
              <><span className="spinner" /> Maskuję dane…</>
            ) : hasRedaction ? (
              <><span className="ico">↻</span> Zamaskuj ponownie</>
            ) : (
              <><span className="ico">⌘</span> Zamaskuj dane</>
            )}
          </button>
        </div>
      </footer>
    </section>
  );
}

// ── OutputPanel ─────────────────────────────────────────────────────────────
function OutputPanel({ originalText, spans, mode, setMode, hiddenLabels, hoveredId, setHoveredId, theme, onCopy, onDownload, copyState, isLoading, error }) {
  const segments = useMemo(() => buildSegments(originalText, spans), [originalText, spans]);

  // Tekst do wyświetlenia w trybie "redacted"
  const renderRedacted = () => (
    <pre className="output-text">
      {segments.map((s, i) => {
        if (s.kind === "text") return <span key={i}>{s.text}</span>;
        const sp = s.span;
        const id = `${sp.start}-${sp.end}`;
        if (hiddenLabels.has(sp.label)) return <span key={i}>{sp.text}</span>;
        const c = chipColor(sp.label, theme);
        const isHover = hoveredId === id;
        return (
          <span
            key={i}
            className={`mask-chip ${isHover ? "is-hover" : ""}`}
            style={{ background: c.bg, color: c.fg, borderColor: c.border }}
            onMouseEnter={() => setHoveredId(id)}
            onMouseLeave={() => setHoveredId(null)}
            title={`${sp.label} · oryginał: ${sp.text}`}
          >
            {sp.placeholder}
          </span>
        );
      })}
    </pre>
  );

  // Tryb "highlight" — pokazuje oryginał z podświetleniami
  const renderHighlight = () => (
    <pre className="output-text">
      {segments.map((s, i) => {
        if (s.kind === "text") return <span key={i}>{s.text}</span>;
        const sp = s.span;
        const id = `${sp.start}-${sp.end}`;
        if (hiddenLabels.has(sp.label)) return <span key={i}>{sp.text}</span>;
        const c = chipColor(sp.label, theme);
        const isHover = hoveredId === id;
        return (
          <mark
            key={i}
            className={`mark ${isHover ? "is-hover" : ""}`}
            style={{ background: c.bg, color: c.fg, boxShadow: `inset 0 -1.5px 0 ${c.border}` }}
            onMouseEnter={() => setHoveredId(id)}
            onMouseLeave={() => setHoveredId(null)}
          >
            {sp.text}
            <sup className="mark-tag">{sp.label}</sup>
          </mark>
        );
      })}
    </pre>
  );

  return (
    <section className="panel output-panel">
      <header className="panel-head">
        <div className="panel-title">
          <span className="dot dot-output" />
          <h2>Bezpieczna wersja</h2>
          <span className="panel-sub">możesz to spokojnie wysłać do Claude / GPT</span>
        </div>
        <div className="panel-actions">
          <div className="seg-control" role="tablist">
            <button
              className={mode === "redacted" ? "seg-active" : ""}
              onClick={() => setMode("redacted")}
            >Zamaskowany</button>
            <button
              className={mode === "highlight" ? "seg-active" : ""}
              onClick={() => setMode("highlight")}
            >Z podświetleniem</button>
          </div>
        </div>
      </header>

      <div className="output-body">
        {error ? (
          <div className="output-error">
            <div className="empty-glyph empty-glyph-err">!</div>
            <p><b>Coś poszło nie tak.</b></p>
            <small>{error}</small>
          </div>
        ) : isLoading ? (
          <div className="output-loading">
            <div className="scan-line" />
            <p>Lokalny model analizuje tekst…</p>
            <small>Pierwsza analiza może potrwać ~30s. Kolejne są natychmiastowe.</small>
          </div>
        ) : spans.length === 0 && !originalText ? (
          <div className="output-empty">
            <div className="empty-glyph">⌘</div>
            <p>Tutaj pojawi się Twój tekst z zamaskowanymi danymi.</p>
            <small>Wklej coś po lewej i kliknij <b>Zamaskuj dane</b>.</small>
          </div>
        ) : spans.length === 0 ? (
          <div className="output-empty">
            <div className="empty-glyph empty-glyph-ok">✓</div>
            <p>Nie wykryto żadnych danych wrażliwych.</p>
            <small>Możesz bezpiecznie wysłać oryginalny tekst.</small>
          </div>
        ) : (
          <>
            {mode === "highlight" && (
              <div className="preview-banner">
                <span className="preview-banner-icon">👁</span>
                <span><b>Tryb weryfikacji</b> — pokazuję oryginał z zaznaczeniami. Kopiowanie i pobieranie zawsze daje wersję zamaskowaną.</span>
              </div>
            )}
            {mode === "redacted" ? renderRedacted() : renderHighlight()}
          </>
        )}
      </div>

      {spans.length > 0 && !isLoading && (
        <footer className="panel-foot">
          <div className="meta">
            <span><b>{spans.length}</b> {spans.length === 1 ? "zmiana" : spans.length < 5 ? "zmiany" : "zmian"}</span>
            <span className="sep">·</span>
            <span>{new Set(spans.map(s => s.placeholder)).size} unikalnych etykiet</span>
          </div>
          <div className="foot-actions">
            <button className="btn-ghost" onClick={onDownload}>
              <span className="ico">↧</span> Pobierz .md
            </button>
            <button className="btn-primary" onClick={onCopy} title="Zawsze kopiuje wersję zamaskowaną — niezależnie od trybu podglądu">
              {copyState === "copied" ? (
                <><span className="ico">✓</span> Skopiowano (bezpieczne)</>
              ) : (
                <><span className="ico">⎘</span> Kopiuj zamaskowane</>
              )}
            </button>
          </div>
        </footer>
      )}
    </section>
  );
}

Object.assign(window, { InputPanel, OutputPanel, buildSegments, chipColor });
