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
const ACCEPTED_EXT = [".txt", ".md", ".markdown", ".csv", ".tsv", ".log", ".json", ".html", ".htm", ".rtf", ".srt", ".vtt"];
const ACCEPT_ATTR = ACCEPTED_EXT.join(",");
const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5 MB

function InputPanel({ text, onChange, onSampleLoad, onRedact, isLoading, hasRedaction, theme }) {
  const charCount = text.length;
  const wordCount = text.trim() ? text.trim().split(/\s+/).length : 0;

  const [mode, setMode] = useState("paste");
  const [uploadedFile, setUploadedFile] = useState(null); // { name, sizeKB, charCount }
  const [pendingReplace, setPendingReplace] = useState(null); // { content, name, sizeKB, charCount }
  const [fileError, setFileError] = useState(null);

  const fileInputRef = useRef(null);
  const textareaRef = useRef(null);
  const uploadTriggerRef = useRef(null);
  const editTextRef = useRef(null);
  const dialogRef = useRef(null);
  const dialogCancelRef = useRef(null);
  const errorCloseRef = useRef(null);

  const dragCounter = useRef(0);
  const [isDragging, setIsDragging] = useState(false);

  // ── File reading ────────────────────────────────────────────────────────
  function validateFile(f) {
    if (!f) return "Brak pliku.";
    const name = (f.name || "").toLowerCase();
    const ext = name.includes(".") ? name.slice(name.lastIndexOf(".")) : "";
    const looksTexty = (f.type && f.type.startsWith("text/")) || ACCEPTED_EXT.includes(ext);
    if (!looksTexty) return `Nieobsługiwany typ pliku: ${ext || f.type || "?"}. Obsługiwane: ${ACCEPTED_EXT.join(", ")}`;
    if (f.size > MAX_FILE_SIZE) return `Plik za duży (${(f.size / 1024 / 1024).toFixed(1)} MB). Limit: 5 MB.`;
    return null;
  }

  function readFile(f) {
    setFileError(null);
    const err = validateFile(f);
    if (err) {
      setFileError(err);
      return;
    }
    const r = new FileReader();
    r.onload = () => {
      const content = String(r.result || "");
      const meta = {
        content,
        name: f.name,
        sizeKB: Math.max(1, Math.round(f.size / 1024)),
        charCount: content.length,
      };
      if (text.trim().length > 0) {
        // Niepusty draft → confirm modal
        setPendingReplace(meta);
      } else {
        applyFile(meta);
      }
    };
    r.onerror = () => setFileError("Nie udało się odczytać pliku.");
    r.readAsText(f);
  }

  function applyFile(meta) {
    onChange(meta.content);
    setUploadedFile({ name: meta.name, sizeKB: meta.sizeKB, charCount: meta.charCount });
  }

  function resetUpload() {
    setUploadedFile(null);
    onChange("");
    setTimeout(() => uploadTriggerRef.current?.focus(), 0);
  }

  function handleFileInputChange(e) {
    readFile(e.target.files?.[0]);
    e.target.value = "";
  }

  // ── Confirm dialog ──────────────────────────────────────────────────────
  useEffect(() => {
    const dlg = dialogRef.current;
    if (!dlg) return;
    if (pendingReplace && !dlg.open) {
      dlg.showModal();
      setTimeout(() => dialogCancelRef.current?.focus(), 0);
    } else if (!pendingReplace && dlg.open) {
      dlg.close();
    }
  }, [pendingReplace]);

  function cancelReplace() {
    setPendingReplace(null);
    setTimeout(() => uploadTriggerRef.current?.focus(), 0);
  }
  function confirmReplace() {
    if (pendingReplace) applyFile(pendingReplace);
    setPendingReplace(null);
    setTimeout(() => editTextRef.current?.focus(), 0);
  }

  // ── Dragging (only active in upload mode) ──────────────────────────────
  function handleDragEnter(e) {
    e.preventDefault();
    e.stopPropagation();
    if (e.dataTransfer && Array.from(e.dataTransfer.types || []).includes("Files")) {
      dragCounter.current += 1;
      setIsDragging(true);
    }
  }
  function handleDragOver(e) {
    e.preventDefault();
    e.stopPropagation();
    if (e.dataTransfer) e.dataTransfer.dropEffect = mode === "upload" ? "copy" : "none";
  }
  function handleDragLeave(e) {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current = Math.max(0, dragCounter.current - 1);
    if (dragCounter.current === 0) setIsDragging(false);
  }
  function handleDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current = 0;
    setIsDragging(false);
    if (mode !== "upload") return; // paste mode = pure intercept
    const f = e.dataTransfer?.files?.[0];
    readFile(f);
  }

  // ── Tab switching ──────────────────────────────────────────────────────
  function activateTab(next) {
    if (next === mode) return;
    setMode(next);
  }

  function onTabKeyDown(e) {
    const order = ["paste", "upload"];
    const idx = order.indexOf(mode);
    if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
      e.preventDefault();
      const dir = e.key === "ArrowRight" ? 1 : -1;
      const next = order[(idx + dir + order.length) % order.length];
      activateTab(next);
    } else if (e.key === "Home") {
      e.preventDefault();
      activateTab(order[0]);
    } else if (e.key === "End") {
      e.preventDefault();
      activateTab(order[order.length - 1]);
    }
  }

  // Focus management on tab change
  useEffect(() => {
    if (mode === "paste") {
      setTimeout(() => textareaRef.current?.focus(), 0);
    } else {
      setTimeout(() => uploadTriggerRef.current?.focus(), 0);
    }
  }, [mode]);

  // Focus on file error
  useEffect(() => {
    if (fileError) setTimeout(() => errorCloseRef.current?.focus(), 0);
  }, [fileError]);

  return (
    <section
      className={`panel input-panel ${isDragging ? "is-dragging" : ""} mode-${mode}`}
      onDragEnter={handleDragEnter}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      <header className="panel-head">
        <div className="panel-title">
          <span className="dot dot-input" />
          <h2>Twój tekst</h2>
          <span className="panel-sub">wybierz sposób wprowadzenia danych</span>
        </div>
        <div className="panel-actions">
          <div role="tablist" aria-label="Sposób dostarczenia danych" className="seg-control input-tabs" onKeyDown={onTabKeyDown}>
            <button
              role="tab"
              id="tab-paste"
              aria-selected={mode === "paste"}
              aria-controls="panel-paste"
              tabIndex={mode === "paste" ? 0 : -1}
              className={mode === "paste" ? "seg-active" : ""}
              onClick={() => activateTab("paste")}
            >
              <span className="ico" aria-hidden="true">⌘V</span> Wklej tekst
            </button>
            <button
              role="tab"
              id="tab-upload"
              aria-selected={mode === "upload"}
              aria-controls="panel-upload"
              tabIndex={mode === "upload" ? 0 : -1}
              className={mode === "upload" ? "seg-active" : ""}
              onClick={() => activateTab("upload")}
            >
              <span className="ico" aria-hidden="true">↥</span> Wgraj plik
            </button>
          </div>
        </div>
      </header>

      {mode === "paste" && (
        <div className="sample-row">
          <span className="sample-label">START:</span>
          {Object.entries(window.SAMPLES).map(([k, s]) => (
            <button key={k} className="sample-pill" onClick={() => onSampleLoad(k)}>
              {s.title}
            </button>
          ))}
        </div>
      )}

      {/* PASTE PANEL */}
      <div
        role="tabpanel"
        id="panel-paste"
        aria-labelledby="tab-paste"
        className="tab-panel textarea-wrap"
        hidden={mode !== "paste"}
      >
        <textarea
          ref={textareaRef}
          className="textarea"
          value={text}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Wklej tutaj fragment maila, transkryptu, notatki głosowej…&#10;&#10;Wszystko zostaje na Twoim komputerze. Tekst nigdy nie opuszcza tej aplikacji."
          spellCheck={false}
        />
        {!text && (
          <div className="textarea-hint">
            <kbd>⌘V</kbd> żeby wkleić · obsługa wielu formatów w zakładce <b>Wgraj plik</b>
          </div>
        )}
        {isDragging && mode === "paste" && (
          <div className="dropzone-overlay dropzone-intercept" aria-hidden="true">
            <div className="dropzone-card">
              <div className="dropzone-glyph">↥</div>
              <p><b>Aby wczytać plik, przejdź do zakładki "Wgraj plik"</b></p>
              <small>(ten panel jest dla wklejanego tekstu)</small>
            </div>
          </div>
        )}
      </div>

      {/* UPLOAD PANEL */}
      <div
        role="tabpanel"
        id="panel-upload"
        aria-labelledby="tab-upload"
        className="tab-panel upload-panel"
        hidden={mode !== "upload"}
      >
        {!uploadedFile ? (
          <div className={`upload-zone ${isDragging && mode === "upload" ? "is-dragging" : ""}`} aria-describedby="upload-hint">
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPT_ATTR}
              onChange={handleFileInputChange}
              hidden
            />
            <button
              ref={uploadTriggerRef}
              type="button"
              className="upload-trigger"
              onClick={() => fileInputRef.current?.click()}
            >
              <span className="upload-glyph" aria-hidden="true">↥</span>
              <span className="upload-cta"><b>Wybierz plik z dysku</b></span>
              <small>lub przeciągnij plik tutaj</small>
            </button>
            <p id="upload-hint" className="upload-formats">
              <code>.md</code> · <code>.txt</code> · <code>.csv</code> · <code>.tsv</code> · <code>.json</code> · <code>.log</code> · <code>.html</code> · <code>.srt</code> · <code>.vtt</code>
              <span className="upload-limit">do 5 MB</span>
            </p>
            <div className="dragging-status" aria-live="polite">
              {isDragging && mode === "upload" ? "Upuść plik aby wczytać." : ""}
            </div>
          </div>
        ) : (
          <div className="upload-success" role="status" aria-live="polite">
            <div className="upload-success-header">
              <span className="upload-success-glyph" aria-hidden="true">✓</span>
              <div className="upload-success-meta">
                <b>Załadowano: {uploadedFile.name}</b>
                <small>{uploadedFile.charCount.toLocaleString("pl-PL")} znaków · {uploadedFile.sizeKB} KB</small>
              </div>
              <div className="upload-success-actions">
                <button
                  ref={editTextRef}
                  className="btn-ghost"
                  onClick={() => activateTab("paste")}
                >
                  <span className="ico" aria-hidden="true">✎</span> Edytuj tekst
                </button>
                <button className="btn-ghost" onClick={resetUpload}>
                  Wgraj inny
                </button>
              </div>
            </div>
            <div className="upload-preview-label">Podgląd zawartości:</div>
            <pre className="upload-preview" tabIndex={0} aria-label="Podgląd zawartości wgranego pliku">
              {text}
            </pre>
          </div>
        )}
      </div>

      {fileError && (
        <div className="file-error" role="alert">
          <span className="warn-icon" aria-hidden="true">⚠</span>
          <span>{fileError}</span>
          <button ref={errorCloseRef} onClick={() => setFileError(null)} aria-label="Zamknij">×</button>
        </div>
      )}

      {/* Confirm replace dialog */}
      <dialog
        ref={dialogRef}
        className="confirm-dialog"
        onCancel={(e) => { e.preventDefault(); cancelReplace(); }}
        onClick={(e) => { if (e.target === dialogRef.current) cancelReplace(); }}
      >
        <h3>Zastąpić istniejący tekst?</h3>
        <p>
          Masz już wpisany tekst (<b>{charCount.toLocaleString("pl-PL")} znaków</b>) w zakładce "Wklej tekst".
          Czy zastąpić go zawartością pliku <b>{pendingReplace?.name}</b>?
        </p>
        <div className="dialog-actions">
          <button ref={dialogCancelRef} className="btn-ghost" onClick={cancelReplace}>
            Anuluj
          </button>
          <button className="btn-primary" onClick={confirmReplace}>
            Zastąp
          </button>
        </div>
      </dialog>

      <footer className="panel-foot">
        <div className="meta">
          <span><b>{charCount.toLocaleString("pl-PL")}</b> znaków</span>
          <span className="sep">·</span>
          <span><b>{wordCount.toLocaleString("pl-PL")}</b> słów</span>
        </div>
        <div className="foot-actions">
          {text && (
            <button className="btn-ghost" onClick={() => { onChange(""); setUploadedFile(null); }}>Wyczyść</button>
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
function OutputPanel({ originalText, spans, totalDetections, mode, setMode, hiddenLabels, hoveredId, setHoveredId, theme, onCopy, onDownload, copyState, isLoading, error, hasRedaction }) {
  const segments = useMemo(() => buildSegments(originalText, spans), [originalText, spans]);
  const allHidden = hasRedaction && (totalDetections || 0) > 0 && spans.length === 0;

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
        ) : !hasRedaction ? (
          <div className="output-empty">
            <div className="empty-glyph">⌘</div>
            <p>Tutaj pojawi się Twój tekst z zamaskowanymi danymi.</p>
            <small>Wklej coś po lewej i kliknij <b>Zamaskuj dane</b>.</small>
          </div>
        ) : allHidden ? (
          <div className="output-empty">
            <div className="empty-glyph empty-glyph-warn">⊘</div>
            <p>Wszystkie wykryte dane są ukryte.</p>
            <small>Włącz kategorie w panelu <b>Wykryte dane</b> po prawej, żeby zobaczyć zamaskowany tekst.</small>
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
