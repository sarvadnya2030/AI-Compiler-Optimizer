const KEYWORDS = new Set(["int", "if", "else", "return"]);
const TOKEN_RE = /\b(int|if|else|return)\b|\b\d+\b|[A-Za-z_]\w*/g;

function escapeHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// Walk the raw source once: escape only the literal text *between* tokens
// (which may contain <, >, &, braces...) and wrap each matched token as-is
// (tokens are always plain [A-Za-z0-9_], so they're already HTML-safe).
// Escaping the whole string up front and then regex-matching over it would
// re-match letters inside entities like "&gt;" (e.g. the "gt") and corrupt
// them -- this single left-to-right pass avoids that entirely.
function highlight(src) {
  let out = "";
  let last = 0;
  let m;
  TOKEN_RE.lastIndex = 0;
  while ((m = TOKEN_RE.exec(src)) !== null) {
    out += escapeHtml(src.slice(last, m.index));
    const tok = m[0];
    if (KEYWORDS.has(tok)) out += `<span class="tok-kw">${tok}</span>`;
    else if (/^\d+$/.test(tok)) out += `<span class="tok-num">${tok}</span>`;
    else out += `<span class="tok-ident">${tok}</span>`;
    last = TOKEN_RE.lastIndex;
  }
  out += escapeHtml(src.slice(last));
  return out;
}

export default function CodeEditor({ value, onChange, filename = "source.c", rows = 12 }) {
  const lineCount = value.split("\n").length;
  const lineNumbers = Array.from({ length: lineCount }, (_, i) => i + 1).join("\n");

  return (
    <div className="editor-frame">
      <div className="editor-titlebar">
        <span className="editor-dot dot-red" />
        <span className="editor-dot dot-yellow" />
        <span className="editor-dot dot-green" />
        <span className="editor-filename">{filename}</span>
      </div>
      <div className="editor-body" style={{ "--rows": rows }}>
        <pre className="editor-gutter" aria-hidden="true">
          {lineNumbers}
        </pre>
        <div className="editor-code-area">
          <pre className="editor-highlight" aria-hidden="true" dangerouslySetInnerHTML={{ __html: highlight(value) + "\n" }} />
          <textarea
            className="editor-input"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            spellCheck={false}
            autoCapitalize="off"
            autoCorrect="off"
            wrap="off"
          />
        </div>
      </div>
    </div>
  );
}
