"""Supervisor LLM research package (learning-lab).

S1 vertical slice:
  snapshot.build(root)  -- read-only fleet snapshot, pure and canaried
  bench.run(code, snap) -- restricted Python analysis over a copy of the snapshot
  core.review(snap,...) -- UI-free supervisor run over local Ollama; records everything
"""