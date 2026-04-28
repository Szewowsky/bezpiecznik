// app.jsx — root komponent aplikacji "Bezpiecznik"

const { useState: useStateApp, useMemo: useMemoApp, useEffect: useEffectApp } = React;

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "theme": "minimal-dark",
  "fontSize": 14,
  "showWarning": "subtle",
  "outputMode": "redacted",
  "panelOpen": true
}/*EDITMODE-END*/;

function App() {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);

  // Stan
  const [text, setText] = useStateApp("");
  const [hasRedaction, setHasRedaction] = useStateApp(false);
  const [isLoading, setIsLoading] = useStateApp(false);
  const [originalText, setOriginalText] = useStateApp("");
  const [spans, setSpans] = useStateApp([]);
  const [hiddenLabels, setHiddenLabels] = useStateApp(new Set());
  const [hoveredId, setHoveredId] = useStateApp(null);
  const [outputMode, setOutputMode] = useStateApp(t.outputMode || "redacted");
  const [copyState, setCopyState] = useStateApp("idle");
  const [activeSampleKey, setActiveSampleKey] = useStateApp(null);
  const [sessionStats, setSessionStats] = useStateApp({ runs: 0, masked: 0 });
  const [warningDismissed, setWarningDismissed] = useStateApp(false);
  const [error, setError] = useStateApp(null);

  // Theme propaguj na <html>
  useEffectApp(() => {
    document.documentElement.dataset.theme = t.theme;
    // Don't size root — only the editor body so chrome stays consistent
  }, [t.theme]);

  useEffectApp(() => {
    document.documentElement.style.setProperty("--editor-font-size", `${t.fontSize}px`);
  }, [t.fontSize]);

  function loadSample(key) {
    const s = window.SAMPLES[key];
    setText(s.text);
    setActiveSampleKey(key);
    setHasRedaction(false);
    setSpans([]);
    setError(null);
  }

  async function runRedaction() {
    if (!text.trim()) return;
    setIsLoading(true);
    setHasRedaction(false);
    setHoveredId(null);
    setError(null);

    try {
      const res = await fetch("/api/redact", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });

      if (!res.ok) {
        let detail = `HTTP ${res.status}`;
        try {
          const err = await res.json();
          if (err && err.detail) detail = err.detail;
        } catch (_) {
          /* ignore */
        }
        throw new Error(detail);
      }

      const data = await res.json();
      const detections = data.detections || [];
      setOriginalText(text);
      setSpans(detections);
      setHasRedaction(true);
      setSessionStats((s) => ({
        runs: s.runs + 1,
        masked: s.masked + detections.length,
      }));
    } catch (e) {
      console.error("Redact failed:", e);
      setError(
        e && e.message
          ? `Nie udało się połączyć z lokalnym backendem (${e.message}). Czy serwer działa na porcie 8000?`
          : "Nie udało się połączyć z lokalnym backendem."
      );
    } finally {
      setIsLoading(false);
    }
  }

  function toggleLabel(label) {
    const next = new Set(hiddenLabels);
    if (next.has(label)) next.delete(label); else next.add(label);
    setHiddenLabels(next);
  }

  // Tekst wynikowy do kopiowania (z aktualnym filtrowaniem)
  const finalText = useMemoApp(() => {
    if (!hasRedaction) return "";
    const visible = spans.filter((s) => !hiddenLabels.has(s.label));
    let out = "";
    let cursor = 0;
    for (const s of visible) {
      out += originalText.slice(cursor, s.start);
      out += s.placeholder;
      cursor = s.end;
    }
    out += originalText.slice(cursor);
    return out;
  }, [hasRedaction, originalText, spans, hiddenLabels]);

  function copyToClipboard() {
    navigator.clipboard.writeText(finalText).then(() => {
      setCopyState("copied");
      setTimeout(() => setCopyState("idle"), 1800);
    }).catch(() => setCopyState("idle"));
  }

  function downloadFile() {
    const blob = new Blob([finalText], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "tekst_zamaskowany.md";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="app">
      <Header sessionStats={sessionStats} theme={t.theme} />

      {t.showWarning !== "off" && !warningDismissed && (
        <WarningStrip
          variant={t.showWarning}
          onDismiss={() => setWarningDismissed(true)}
        />
      )}

      <main className="workspace">
        <InputPanel
          text={text}
          onChange={(v) => { setText(v); if (hasRedaction) { /* keep result */ } }}
          onSampleLoad={loadSample}
          onRedact={runRedaction}
          isLoading={isLoading}
          hasRedaction={hasRedaction}
          theme={t.theme}
        />
        <OutputPanel
          originalText={originalText || text}
          spans={hasRedaction ? spans.filter((s) => !hiddenLabels.has(s.label)) : []}
          mode={outputMode}
          setMode={setOutputMode}
          hiddenLabels={hiddenLabels}
          hoveredId={hoveredId}
          setHoveredId={setHoveredId}
          theme={t.theme}
          onCopy={copyToClipboard}
          onDownload={downloadFile}
          copyState={copyState}
          isLoading={isLoading}
          error={error}
        />
        <DetectionPanel
          spans={hasRedaction ? spans : []}
          hiddenLabels={hiddenLabels}
          toggleLabel={toggleLabel}
          hoveredId={hoveredId}
          setHoveredId={setHoveredId}
          theme={t.theme}
        />
      </main>

      <Footer theme={t.theme} />

      <TweaksPanel>
        <TweakSection label="Wygląd" />
        <TweakRadio
          label="Motyw"
          value={t.theme}
          options={[
            { value: "minimal-dark", label: "Minimal" },
            { value: "terminal", label: "Terminal" },
            { value: "light", label: "Light" },
          ]}
          onChange={(v) => setTweak("theme", v)}
        />
        <TweakSlider
          label="Rozmiar tekstu"
          value={t.fontSize} min={12} max={18} step={1} unit="px"
          onChange={(v) => setTweak("fontSize", v)}
        />
        <TweakSection label="Banner ostrzegawczy" />
        <TweakRadio
          label="Widoczność"
          value={t.showWarning}
          options={[
            { value: "subtle", label: "Subtelnie" },
            { value: "prominent", label: "Wyraźnie" },
            { value: "off", label: "Ukryj" },
          ]}
          onChange={(v) => { setTweak("showWarning", v); setWarningDismissed(false); }}
        />
        <TweakSection label="Stan demo" />
        <TweakButton onClick={() => { setText(""); setSpans([]); setHasRedaction(false); setActiveSampleKey(null); }}>
          Wyczyść wszystko
        </TweakButton>
        <TweakButton onClick={() => loadSample("email")}>
          Wczytaj przykład
        </TweakButton>
      </TweaksPanel>
    </div>
  );
}

// ── Header ─────────────────────────────────────────────────────────────────
function Header({ sessionStats, theme }) {
  return (
    <header className="app-header">
      <div className="brand">
        <div className="brand-mark" aria-hidden="true">
          <svg viewBox="0 0 28 28" width="28" height="28">
            <rect x="6" y="12" width="16" height="11" rx="2" fill="none" stroke="currentColor" strokeWidth="1.5"/>
            <path d="M9 12 V8 a5 5 0 0 1 10 0 V12" fill="none" stroke="currentColor" strokeWidth="1.5"/>
            <circle cx="14" cy="17.5" r="1.4" fill="currentColor"/>
          </svg>
        </div>
        <div className="brand-text">
          <h1>Bezpiecznik <span className="h1-tag">v0.2 · local</span></h1>
          <small>lokalny strażnik danych wrażliwych — przed wysłaniem do AI</small>
        </div>
      </div>

      <div className="header-status">
        <div className="status-pill status-local">
          <span className="status-led" />
          <span><b>Wszystko lokalnie</b><em>· 0 połączeń sieciowych</em></span>
        </div>
        {sessionStats.runs > 0 && (
          <div className="status-stats">
            <span><b>{sessionStats.runs}</b><span>{sessionStats.runs === 1 ? "analiza" : "analiz"}</span></span>
            <span><b>{sessionStats.masked}</b><span>zamaskowanych</span></span>
          </div>
        )}
      </div>
    </header>
  );
}

// ── Warning ────────────────────────────────────────────────────────────────
function WarningStrip({ variant, onDismiss }) {
  if (variant === "subtle") {
    return (
      <div className="warn-strip warn-subtle">
        <span className="warn-icon" aria-hidden="true">⚠</span>
        <span className="warn-text">
          Najlepiej wykrywa <b>osoby, e-mail, telefon, IBAN, NIP, PESEL</b>. Nazwy firm bez sufiksów (Sp. z o.o., S.A.) i polska fleksja imion mogą wymagać <b>ręcznej kontroli</b>.
        </span>
        <button onClick={onDismiss} aria-label="Zamknij">×</button>
      </div>
    );
  }
  return (
    <div className="warn-strip warn-prominent">
      <div className="warn-prom-body">
        <span className="warn-icon" aria-hidden="true">⚠</span>
        <div className="warn-text">
          <b>Output wymaga ręcznej weryfikacji</b>
          <p>Najlepiej wykrywa: osoby, e-mail, telefon, IBAN, NIP, PESEL. <b>Znane limity:</b> nazwy firm bez sufiksów (np. "Brandbox"), polska fleksja imion (np. "Pawłem"), ulice mogą być mylone z osobami. To narzędzie minimalizuje ryzyko, ale nie jest certyfikatem zgodności - RODO wymaga umowy DPA dla dostawców z USA.</p>
        </div>
      </div>
      <button onClick={onDismiss} className="warn-close" aria-label="Zamknij">×</button>
    </div>
  );
}

// ── Footer ─────────────────────────────────────────────────────────────────
function Footer() {
  return (
    <footer className="app-foot">
      <div className="foot-left">
        <span className="kbd-row">
          <kbd>⌘</kbd><kbd>Enter</kbd> <em>analiza</em>
        </span>
        <span className="kbd-row">
          <kbd>⌘</kbd><kbd>C</kbd> <em>kopiuj wynik</em>
        </span>
      </div>
      <div className="foot-right">
        <span>Model: <b>OpenAI Privacy Filter</b> + regex PL</span>
        <span className="sep">·</span>
        <span>Działa w pełni offline</span>
      </div>
    </footer>
  );
}

// ── Mount ──────────────────────────────────────────────────────────────────
const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App />);

// Skróty klawiszowe
window.addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
    document.querySelector(".btn-primary:not(:disabled)")?.click();
  }
});
