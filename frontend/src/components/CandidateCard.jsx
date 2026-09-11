import { useState } from "react";

function formatIr(ir) {
  return ir.instructions
    .map((i) => {
      if (i.op === "RETURN") return `return ${i.value}`;
      if (i.op === "CONST") return `${i.dest} = ${i.value}`;
      if (i.op === "CMP") return `${i.dest} = cmp.${i.cmp} ${i.lhs}, ${i.rhs}`;
      if (i.op === "SELECT") return `${i.dest} = select ${i.cond} ? ${i.then} : ${i.else}`;
      return `${i.dest} = ${i.op.toLowerCase()} ${i.lhs}, ${i.rhs}`;
    })
    .join("\n");
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    } catch {
      // clipboard unavailable -- silently no-op
    }
  }

  return (
    <button className="copy-btn" onClick={handleCopy} title="Copy IR">
      {copied ? "copied" : "copy"}
    </button>
  );
}

function IrBlock({ ir }) {
  if (!ir) return null;
  const text = formatIr(ir);
  return (
    <div className="ir-block-wrapper">
      <pre className="ir-block">{text}</pre>
      <CopyButton text={text} />
    </div>
  );
}

export default function CandidateCard({ candidate, originalIr, index }) {
  const accepted = candidate.accepted;
  const verification = candidate.verification;
  const status = verification ? verification.status : "PARSE_ERROR";

  const statusClass = accepted ? "status-accepted" : "status-rejected";

  return (
    <div className={`candidate-card ${statusClass}`}>
      <div className="candidate-header">
        <span className="candidate-title">Candidate #{index + 1}</span>
        <span className={`badge ${statusClass}`}>{accepted ? "✓ ACCEPTED" : "✗ REJECTED"}</span>
      </div>

      <div className="ir-columns">
        <div>
          <div className="ir-label">Original IR</div>
          <IrBlock ir={originalIr} />
        </div>
        <div>
          <div className="ir-label">Optimized IR</div>
          {candidate.candidate_ir ? (
            <IrBlock ir={candidate.candidate_ir} />
          ) : (
            <pre className="ir-block error-block">{candidate.parse_error}</pre>
          )}
        </div>
      </div>

      {verification && (
        <div className="verification-block">
          <div className={`verification-status ${statusClass}`}>
            {accepted ? "✓ EQUIVALENT" : `✗ ${status}`}
          </div>
          <div className="verification-meta">
            <span>Z3: {verification.z3_result.toUpperCase()}</span>
            <span>Verification time: {verification.verification_time_ms} ms</span>
            {candidate.metrics && (
              <span>Instruction reduction: {candidate.metrics.instruction_reduction_pct}%</span>
            )}
          </div>

          {verification.counterexample && (
            <div className="counterexample">
              <div className="counterexample-title">Counterexample</div>
              <div>
                {Object.entries(verification.counterexample.inputs).map(([k, v]) => (
                  <span key={k} className="input-chip">
                    {k} = {v}
                  </span>
                ))}
              </div>
              <div className="counterexample-outputs">
                <span>Original output: {verification.counterexample.original_output}</span>
                <span>Optimized output: {verification.counterexample.optimized_output}</span>
              </div>
            </div>
          )}

          {verification.error_message && !verification.counterexample && (
            <div className="error-message">{verification.error_message}</div>
          )}
        </div>
      )}
    </div>
  );
}
