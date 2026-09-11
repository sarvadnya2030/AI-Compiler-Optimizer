const STAGES = ["source", "lexer", "parser", "ir", "z3", "verdict"];

const LABELS = {
  source: "SOURCE",
  lexer: "LEXER",
  parser: "PARSER",
  ir: "IR (SSA)",
  z3: "Z3 SMT",
  verdict: "VERDICT",
};

export default function PipelineDiagram({ activeStage, doneStage }) {
  const activeIdx = STAGES.indexOf(activeStage);
  const doneIdx = STAGES.indexOf(doneStage);

  return (
    <div className="pipeline">
      {STAGES.map((stage, i) => {
        const isActive = i === activeIdx;
        const isDone = doneIdx >= 0 && i <= doneIdx;
        return (
          <div className="pipeline-item" key={stage}>
            <div
              className={`pipeline-chip ${isActive ? "pipeline-chip-active" : ""} ${
                isDone ? "pipeline-chip-done" : ""
              }`}
            >
              {LABELS[stage]}
            </div>
            {i < STAGES.length - 1 && <span className="pipeline-arrow">→</span>}
          </div>
        );
      })}
    </div>
  );
}
