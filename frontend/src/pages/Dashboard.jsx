import { useEffect, useState } from "react";
import ConfigPanel from "../components/ConfigPanel";
import CandidateCard from "../components/CandidateCard";
import { getHealth, postOptimize } from "../api/client";

const DEFAULT_PROGRAM = `fn compute(x, y) {
    t1 = x + 0;
    t2 = t1 * 1;
    t3 = t2 + t2;
    return t3 + y;
}`;

export default function Dashboard() {
  const [program, setProgram] = useState(DEFAULT_PROGRAM);
  const [config, setConfig] = useState({ llmBackend: "mock", ollamaModel: "qwen3:0.6b", numCandidates: 5 });
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [health, setHealth] = useState(null);

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => setHealth(null));
  }, []);

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
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="dashboard">
      <header className="app-header">
        <h1>AI Compiler Optimizer</h1>
        <p className="subtitle">LLM-Generated Optimizations with Formal Equivalence Verification</p>
        {health && (
          <p className="health-line">
            backend: <strong>{health.status}</strong> · llm: <strong>{health.llm_backend}</strong>
          </p>
        )}
      </header>

      <section className="panel">
        <div className="panel-title">Original Program</div>
        <textarea
          className="code-editor"
          value={program}
          onChange={(e) => setProgram(e.target.value)}
          spellCheck={false}
          rows={10}
        />
      </section>

      <section className="panel">
        <div className="panel-title">Configuration</div>
        <ConfigPanel config={config} onChange={setConfig} onGenerate={handleGenerate} loading={loading} />
      </section>

      {error && <div className="global-error">Error: {error}</div>}

      {report && (
        <section className="panel">
          <div className="panel-title">
            Results — {report.summary.accepted}/{report.summary.total_candidates} accepted (
            {report.summary.acceptance_rate_pct}%)
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
