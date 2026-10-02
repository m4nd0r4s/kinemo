# AI evaluation

Measures the spec's "Designed for AI" goal: a model generates the scene for a natural-language
request using **only** `docs/llms.txt` and `kinemo check`, and the scene must pass
`kinemo check --strict` within **two iterations**. v1.0 target: ≥ 90% of the 50 requests.

- `prompts.txt`: the 50 requests (`id | description`).
- `runs/<id>.py`: the generated scene (the final version).
- `results.json`: `[{"id", "iterations", "passed", "codes"}]` recorded by whoever ran it.
- `python tests/ai_eval/summary.py`: re-checks each scene in `runs/` with `check --strict` and
  summarizes the success rate together with `results.json`.

Protocol for the author (person or agent): read `docs/llms.txt`; write the scene; run
`kinemo check --json --strict`; if it fails, apply the indicated fixes and run it again (that is
the second and last iteration). Do not read the kinemo source code.
