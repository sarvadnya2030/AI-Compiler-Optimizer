// "" (relative, via the Vite dev-server proxy) is a valid, intentional value --
// only fall back to the default when the var is genuinely unset.
const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = (data && data.detail) || res.statusText;
    throw new Error(detail);
  }
  return data;
}

export function getHealth() {
  return request("/api/health");
}

export function getBenchmarks() {
  return request("/api/benchmarks");
}

export function postOptimize({ program, numCandidates, llmBackend, ollamaModel }) {
  return request("/api/optimize", {
    method: "POST",
    body: JSON.stringify({
      program,
      num_candidates: numCandidates,
      llm_backend: llmBackend,
      ollama_model: ollamaModel || undefined,
    }),
  });
}

export function postVerify({ originalProgram, optimizedProgram }) {
  return request("/api/verify", {
    method: "POST",
    body: JSON.stringify({
      original_program: originalProgram,
      optimized_program: optimizedProgram,
    }),
  });
}
