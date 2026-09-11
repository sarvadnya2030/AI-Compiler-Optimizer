import { useEffect, useState } from "react";
import CodeEditor from "../components/CodeEditor";
import ConfigPanel from "../components/ConfigPanel";
import CandidateCard from "../components/CandidateCard";
import ThemeToggle from "../components/ThemeToggle";
import PipelineDiagram from "../components/PipelineDiagram";
import BuildLog from "../components/BuildLog";
import { getHealth, postOptimize } from "../api/client";

const EXAMPLES = {
  "Redundant computation": `int compute(int x, int y) {
    int t1 = x + 0;
    int t2 = t1 * 1;
    int t3 = t2 + t2;
    return t3 + y;
}`,
  "Max (if/else)": `int maxi(int x, int y) {
    if (x > y) {
        return x;
    } else {
        return y;
    }
}`,
  "Abs value (early return)": `int abs_val(int x) {
    if (x < 0) {
        return 0 - x;
    }
    return x;
}`,
  "Sign (else-if chain)": `int sign(int x) {
    if (x > 0) {
        return 1;
    } else if (x < 0) {
        return 0 - 1;
    } else {
        return 0;
    }
}`,
  "Ternary": `int abs_val(int x) {
    return x < 0 ? 0 - x : x;
}`,
};

const DEFAULT_PROGRAM = EXAMPLES["Redundant computation"];

export default function Dashboard() {
  const [program, setProgram] = useState(DEFAULT_PROGRAM);
  const [exampleName, setExampleName] = useState("Redundant computation");
  const [config, setConfig] = useState({ llmBackend: "mock", ollamaModel: "qwen3:0.6b", numCandidates: 5 });
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [health, setHealth] = useState(null);
  const [healthError, setHealthError] = useState(false);
  const [activeStage, setActiveStage] = useState("source");

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => setHealthError(true));
  }, []);

  function handleExampleChange(name) {
    setExampleName(name);
    setProgram(EXAMPLES[name]);
    setReport(null);
    setError(null);
    setActiveStage("source");
  }

  async function handleGenerate() {
    setLoading(true);
    setError(null);
    setReport(null);
    try {
      const data = await postOptimize({
        program,
        numCandidates: config.numCandidates,
        llmBackend: config.llmBackend,
        ollamaModel: config.ollamaModel,
      });
      setReport(data);
      setActiveStage("verdict");
    } catch (e) {
      setError(e.message);
      setActiveStage("source");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="dashboard">
      <header className="app-header">
        <div className="app-header-top">
          <div>
            <h1>
              <span className="brand-mono">mini-C</span> Compiler Optimizer
            </h1>
            <p className="subtitle">LLM-Generated Optimizations with Formal Equivalence Verification</p>
          </div>
          <ThemeToggle />
        </div>
        <div className="status-line">
          <span className={`status-dot ${healthError ? "status-dot-bad" : health ? "status-dot-ok" : ""}`} />
          {healthError ? (
            <span>backend unreachable</span>
          ) : health ? (
            <span>
              backend <strong>{health.status}</strong> · llm <strong>{health.llm_backend}</strong>
            </span>
          ) : (
            <span>connecting…</span>
          )}
        </div>
      </header>

      <PipelineDiagram activeStage={loading ? activeStage : null} doneStage={report ? "verdict" : null} />

      <div className="main-grid">
        <section className="panel editor-panel">
          <div className="panel-title-row">
            <div className="panel-title">Source</div>
            <select
              className="example-picker"
              value={exampleName}
              onChange={(e) => handleExampleChange(e.target.value)}
            >
              {Object.keys(EXAMPLES).map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </div>
          <CodeEditor
            value={program}
            onChange={(v) => {
              setProgram(v);
              setExampleName("");
            }}
            rows={12}
          />
          <BuildLog running={loading} onStageChange={setActiveStage} />
        </section>

        <section className="panel config-panel-wrapper">
          <div className="panel-title">Compiler flags</div>
          <ConfigPanel config={config} onChange={setConfig} onGenerate={handleGenerate} loading={loading} />
        </section>
      </div>

      {error && (
        <div className="global-error">
          <span className="error-icon">⚠</span> {error}
        </div>
      )}

      {report && (
        <section className="panel results-panel">
          <div className="results-header">
            <div className="panel-title">Verification results</div>
            <div className={`results-badge ${report.summary.accepted > 0 ? "results-badge-ok" : "results-badge-none"}`}>
              {report.summary.accepted}/{report.summary.total_candidates} accepted ({report.summary.acceptance_rate_pct}%)
            </div>
          </div>
          <div className="candidate-list">
            {report.candidates.map((c) => (
              <CandidateCard key={c.index} candidate={c} originalIr={report.original_ir} index={c.index} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
