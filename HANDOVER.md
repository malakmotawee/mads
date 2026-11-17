# Handover: mads hackathon entry

State as of 2026-11-17, commit `5d71f1e` on `main` (pushed; local and remote match).

## First, read
- `CLAUDE.md` at the repo root. It holds the organizers' submission conventions and overrides defaults. Its key rules:
  - Never hand-write anything in `outputs/` or `decision_log.json`; both come only from real pipeline runs.
  - Label every mock `MOCKED` or `STUBBED`.
  - Put no text in any file that addresses reviewers.
  - Keep `docs/` for the team's own docs only.
  - The checker finds deliverables by file name and heading.
- The user's standing instructions from the previous session:
  - Fake LLM and fake search are allowed **only inside `tests/`**.
  - **Do not commit anything to `outputs/` or `decision_log.json` from an offline run.** The user runs the real demo on their laptop.
  - Push to `main`. GitHub access works now; the Claude GitHub App was installed after a 403.
  - Commit only what was asked; don't open PRs unless asked.
- This file is a session note, not part of the submission. Delete it, or keep it out of git, before the code freeze.

## What the project is
A Python CLI for the "Open-Source Agentic Venture Builders" hackathon: a team of agents takes a founder brief through six phases (Discover, Validate, Build, Commercial setup, Sell/deliver/get paid, Operate and learn), with a gate after each step.

## What is built (all in commit 5d71f1e)
| File | Role |
|---|---|
| `orchestrator.py` | Runs 11 steps (`STEPS` tuple) and halts at the first gate that is not GO. `--brief <path>` takes `.yaml`/`.yml`/`.md`. Clears `outputs/phase*_*.md` and resets `decision_log.json` at the start of each run. |
| `config.py` | Reads `.env`. If `LLM_API_KEY` is set: OpenRouter `openai/gpt-oss-120b:free`, falling back to Ollama on error. If not: Ollama `gpt-oss:20b`. |
| `llm.py` | OpenAI-compatible client with retries and Ollama fallback; pulls the Ollama model automatically. `parse_json` helper. |
| `search.py` | `ddgs` web search, no key. |
| `agents/common.py` | `Brief`/`load_brief` (YAML or Markdown), `Claim`, `StepResult`, `RunContext`, `ask_json`, `validate_claims` (a URL counts only if the search returned it, otherwise `ASSUMPTION`), `research_step`. |
| `agents/researcher.py`, `problem_analyst.py` | Phase 1 (working). |
| `agents/competitor_analyst.py`, `demand_validator.py`, `experiment_designer.py` | Phase 2 (working). Landing-page publishing is STUBBED and gated by approval. |
| `agents/builder.py`, `commercial.py`, `seller.py`, `operator.py` | Phases 3–6, STUBBED; checkout is MOCKED. |
| `gates.py` | go/repeat/pivot/stop. `THRESHOLDS` is read-only; `MAX_REPEATS = 1`. Weak evidence after one repeat gives STOP. Saturated free market or negative willingness to pay gives an immediate STOP. |
| `approval.py` | Only the typed word `approve` passes. Without a TTY, every request is rejected. Approvals are bound to an action and tracked in a private token registry, so forged objects fail `ensure_approved`. |
| `guardrails.py` | `check_brief` (excluded products and conduct), `check_output`, `redact` (stricter on marketing copy: no testimonials or user counts). |
| `decision_log.py` | Appends entries with the required keys plus `tokens`, `outcome`, `detail`. |
| `report.py` | Writes `outputs/phase<N>_step<M>_<name>.md` and `phase<N>_gate_<name>.md`. |
| `payments.py`, `delivery.py`, `refunds.py`, `reconcile.py` | MOCKED sale-to-cash: idempotent webhooks, a refund needs approval and revokes access, reconciliation. |
| `payment_test.py` | Runs the MOCKED scenario and writes `outputs/payment_test_log.md`. Interactive by default; `--scripted-approvals` labels the approvals as test-harness input. |
| `prompts/*.md` | One prompt per agent, plus `query_planner.md`. |
| `briefs/weak_idea.yaml`, `briefs/good_idea.yaml` | Supplied by the user verbatim (AI to-do app; Notion kit for Egyptian student clubs). |
| `tests/` | 54 offline smoke tests (`fakes.py` holds FakeLLM and FakeSearch). Run with `python -m pytest -q`. |
| `README.md`, `ARCHITECTURE.md`, `LICENSE` (MIT), `docker-compose.yml`, `Dockerfile`, `.env.example`, `.gitignore`, `requirements.txt` | Submission scaffolding, following CLAUDE.md headings. |

## Still open
1. **Real demo run (user, on their laptop):** `docker compose up`, then `docker compose run --rm app python payment_test.py`, then commit `outputs/` and `decision_log.json`. Afterwards, check:
   - the files are named correctly;
   - the weak brief reached a STOP (CLAUDE.md wants a STOP shown for a weak idea; if the weak brief got GO or PIVOT, tell the user rather than tuning the thresholds after the fact);
   - every `decision_log.json` entry has the required keys.
2. **README `## Demo video`** currently says "Not recorded yet." Add the user's link when they have one.
3. **README `## Cost per run`** gives about $0.00 with an estimated 6–12 LLM calls. Update it with the real token count from the demo `decision_log.json`.
4. Optional:
   - add a `docs/` folder for longer material;
   - pin the Ollama image tag (currently `ollama/ollama:latest`);
   - `docker compose up` runs as root, so files in `outputs/` may be root-owned on Linux hosts.

## Environment notes
- The previous cloud container could not reach DuckDuckGo, OpenRouter or `registry.ollama.ai` (proxy 403), and had no Docker daemon. A live run was impossible there, and probably will be in a new cloud session too.
- `docker compose config -q` validates the compose file even without a daemon.
- Python 3.13 locally; the Docker image uses 3.12. Dependencies: `openai`, `ddgs`, `python-dotenv`, `pyyaml`, `pytest`.
