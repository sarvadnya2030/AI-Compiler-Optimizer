export default function ConfigPanel({ config, onChange, onGenerate, loading }) {
  return (
    <div className="config-panel">
      <div className="config-field">
        <label>LLM</label>
        <select
          value={config.llmBackend}
          onChange={(e) => onChange({ ...config, llmBackend: e.target.value })}
        >
          <option value="mock">Mock (offline)</option>
          <option value="ollama">Ollama</option>
        </select>
      </div>

      {config.llmBackend === "ollama" && (
        <div className="config-field">
          <label>Model</label>
          <input
            type="text"
            value={config.ollamaModel}
            onChange={(e) => onChange({ ...config, ollamaModel: e.target.value })}
            placeholder="qwen3:0.6b"
          />
        </div>
      )}

      <div className="config-field">
        <label>Candidates</label>
        <input
          type="number"
          min="1"
          max="20"
          value={config.numCandidates}
          onChange={(e) => onChange({ ...config, numCandidates: Number(e.target.value) })}
        />
      </div>

      <button className="generate-btn" onClick={onGenerate} disabled={loading}>
        {loading ? (
          <>
            <span className="spinner" aria-hidden="true" />
            GENERATING…
          </>
        ) : (
          "GENERATE OPTIMIZATIONS"
        )}
      </button>
    </div>
  );
}
