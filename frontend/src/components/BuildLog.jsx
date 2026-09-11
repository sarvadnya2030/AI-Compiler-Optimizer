import { useEffect, useState } from "react";

const STEPS = [
  { stage: "lexer", line: "$ lexing source.c" },
  { stage: "parser", line: "$ parsing tokens -> AST" },
  { stage: "ir", line: "$ lowering AST -> SSA IR" },
  { stage: "ir", line: "$ generating candidates" },
  { stage: "z3", line: "$ encoding IR -> Z3 formula" },
  { stage: "z3", line: "$ z3 solve (checking equivalence)" },
];

/** Animates through fake-but-accurate compiler stage lines while a real
 * request is in flight. Calls onStageChange as it advances so the
 * pipeline diagram above can highlight in sync. */
export default function BuildLog({ running, onStageChange }) {
  const [visible, setVisible] = useState(0);

  useEffect(() => {
    if (!running) {
      setVisible(0);
      return;
    }
    setVisible(1);
    onStageChange?.(STEPS[0].stage);
    let i = 1;
    const id = setInterval(() => {
      if (i >= STEPS.length) {
        clearInterval(id);
        return;
      }
      setVisible(i + 1);
      onStageChange?.(STEPS[i].stage);
      i += 1;
    }, 220);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [running]);

  if (!running) return null;

  return (
    <div className="build-log">
      {STEPS.slice(0, visible).map((s, i) => (
        <div key={i} className="build-log-line">
          {s.line}
        </div>
      ))}
      <div className="build-log-cursor">▌</div>
    </div>
  );
}
