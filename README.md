# mads: an open-source agent team from founder idea to validated digital product

A Python CLI that runs a founder's idea through six phases (Discover, Validate, Build, Commercial setup, Sell/deliver/get paid, Operate and learn) with an evidence gate after every step. Every phase does real work with a free open-weight model: Discover and Validate use free web search; Build drafts the MVP and tests it in code; Commercial setup drafts the price and policies; Launch drafts the store page and posts; Operate drafts the support plan and a persevere-or-pivot memo. Every market claim cites a URL the search actually returned, or is labelled `ASSUMPTION`. Publishing is **STUBBED**; payments and delivery are **MOCKED**, with no payment provider or sandbox of any kind. Nothing is published, sent or spent without the founder typing `approve`.

The gates are built so the system can't flatter an idea. Thresholds are fixed in `gates.py` before any run, and metrics are computed in code from validated claims, never by the model. A weak idea gets a recommendation to **STOP**. A search outage halts the run as "search unavailable" instead of becoming a verdict. The one threshold changed after a real run is logged, with the reason, in `ARCHITECTURE.md`.

## Quickstart

```bash
docker compose up
```

This runs the pipeline on the sample brief `briefs/weak_idea.yaml`. Without an API key it runs fully local: Docker starts Ollama and the app pulls `gpt-oss:20b` (about 13 GB, first run only). Progress and every gate decision print in the terminal. When the run ends, open the results:

- `outputs/`: one Markdown file per step (`phase<N>_step<M>_<name>.md`) and per gate (`phase<N>_gate_<name>.md`)
- `decision_log.json`: one entry per agent action

**Use the free OpenRouter model instead (faster, no download).** Get a free key at <https://openrouter.ai/keys>, then copy the settings template:

```bash
cp .env.example .env
```

Open `.env` and set `LLM_API_KEY=` to your key. Leave `LLM_MODEL=nvidia/nemotron-3-ultra-550b-a55b:free`. `.env` is listed in `.gitignore`, so the key is never committed. Then run `docker compose up` again. If OpenRouter fails (a rate limit or a bad key), the app falls back to local Ollama.

**Run with no local model at all.** Also set `LLM_FALLBACK_TO_OLLAMA=false` in `.env`, and start only the app container, so Ollama is never started and no model is downloaded:

```bash
docker compose run --rm --no-deps app
```

A run then fails with an error instead of falling back if OpenRouter refuses a request.

**Approve steps as the founder.** `docker compose up` has no interactive terminal, so every approval is **rejected** automatically and nothing is published. To approve or reject at the prompt, run the app interactively:

```bash
docker compose run --rm app
```

**Other commands:**

Run another brief. `--brief` takes any YAML (`.yaml`/`.yml`) or Markdown brief file; `briefs/good_idea.yaml` is a second sample:

```bash
docker compose run --rm app python orchestrator.py --brief briefs/good_idea.yaml
```

```bash
BRIEF=briefs/good_idea.yaml docker compose up
```

```bash
docker compose run --rm app python payment_test.py
```

```bash
docker compose run --rm app python -m pytest -q
```

Without Docker: `pip install -r requirements.txt`, then `python orchestrator.py --brief briefs/weak_idea.yaml`. You need a key in `.env`, or Ollama running on `localhost:11434`.

## What works and what is mocked

| Phase / step | What it does | Status |
|---|---|---|
| Brief screen | Guardrails reject excluded products, fake reviews, income promises and impersonation before any agent runs | **Working** |
| 1.1 Opportunities (`agents/researcher.py`) | Plans queries, searches the web (ddgs), extracts pain-point claims with source URLs | **Working** |
| 1.2 Problem (`agents/problem_analyst.py`) | Problem statement built only from step 1.1 claims, with open assumptions listed | **Working** |
| 2.1 Competitors (`agents/competitor_analyst.py`) | Paid competitors, free alternatives and sourced price points | **Working** |
| 2.2 Demand (`agents/demand_validator.py`) | Evidence for and against willingness to pay | **Working** |
| 2.3 Validation plan (`agents/experiment_designer.py`) | Lean Canvas, smoke-test copy and success criteria fixed in advance; publishing the page | Drafting **Working**, publishing **STUBBED** |
| Gates (`gates.py`) | go / repeat / pivot / stop with thresholds fixed in advance | **Working** |
| Founder approval (`approval.py`) | CLI approve/reject before anything is published, sent or spent | **Working** |
| Decision log (`decision_log.py`) | One entry per agent action in `decision_log.json` | **Working** |
| 3.1 Build (`agents/builder.py`) | Drafts the MVP content and user guide; code runs acceptance checks and the gate needs them all to pass | Drafting and tests **Working**, shipping **STUBBED** |
| 4.1 Price and policies (`agents/commercial.py`) | Price from sourced competitor prices (unsourced reasoning labelled `ASSUMPTION`); draft terms, privacy and refund policies, marked as drafts and not legal advice | **Working** |
| 5.1 Store page and launch posts (`agents/commercial.py`) | Drafted, screened by guardrails, "published" only after approval, nowhere real | Drafting **Working**, publishing **STUBBED** |
| 5.2 Checkout (`payments.py`, `agents/seller.py`) | Mock checkout created after approval; no payment provider or sandbox | **MOCKED** |
| 5.3 Delivery (`delivery.py`) | Access granted on a payment webhook, idempotent, revoked on refund | **MOCKED** |
| Refunds (`refunds.py`) | Only with founder approval; revokes access | **MOCKED** |
| Reconciliation (`reconcile.py`) | Matches orders, payments, fees, refunds and payouts | **MOCKED** |
| 6.1 Operate and learn (`agents/operator.py`) | Metrics, support plan and a persevere-or-pivot memo from the Phase 2 criteria; no live data is connected | Drafting **Working**, live data **STUBBED** |

## Architecture

`orchestrator.py` runs eleven steps across the six phases. After each step, `gates.py` scores metrics computed in code (sourced claims, distinct domains, pain and willingness-to-pay signals) against thresholds fixed before the run. A gate either lets the run continue (GO), re-runs the step once with new queries (REPEAT), or halts with PIVOT or STOP. A claim counts as sourced only if its URL was among the search results; any other URL is relabelled `ASSUMPTION`. Outward-facing actions call `approval.ensure_approved`, which only an approval the founder typed can pass. See [ARCHITECTURE.md](ARCHITECTURE.md) for diagrams, gate rules and the sale-to-cash flow.

## Models and free resources

- **Default:** `nvidia/nemotron-3-ultra-550b-a55b:free` (NVIDIA Nemotron 3 Ultra, open weights) on OpenRouter's free tier. It needs a free key in `.env`.
- **Backup:** `nvidia/nemotron-3.5-super-vl:free`, also open-weight. Free models are sometimes throttled by their provider (HTTP 429); set `LLM_MODEL` to the backup and run again.
- **Which free models exist changes often.** List the current ones with `docker compose run --rm --no-deps app python -c "import json,urllib.request; [print(m['id']) for m in json.load(urllib.request.urlopen('https://openrouter.ai/api/v1/models'))['data'] if m['id'].endswith(':free')]"`.
- **Fallback, no key needed:** `gpt-oss:20b` via Ollama, run locally by `docker-compose.yml`. It needs about 16 GB of RAM; a GPU is optional.
- **Other free open-weight models:** set `LLM_MODEL` to another OpenRouter id ending in `:free` (for example a Gemma or Qwen model), or `OLLAMA_MODEL` to a smaller local model such as `qwen3:8b` for machines with less RAM.
- **Free only, enforced in code:** `config.py` refuses any OpenRouter model whose id does not end in `:free`, unless `ALLOW_PAID_MODEL=true` and a price in `LLM_USD_PER_1M_TOKENS` are both set, so a run can't be billed by accident.
- **Free-tier limits:** OpenRouter caps free models at 20 requests per minute and 50 requests per day on an account that has bought no credits. One run uses about 6–16 requests.
- **Any OpenAI-compatible endpoint:** set `LLM_BASE_URL`, `LLM_API_KEY` and `LLM_MODEL` in `.env`.
- **Web search:** the `ddgs` library (DuckDuckGo and other public engines). No key, no cost.
- No paid service is required at any step.

## Cost per run

About $0.00 per run: the free OpenRouter tier or a local model, plus free search. The committed demo run (weak brief, STOP at step 2.1, `nvidia/nemotron-3.5-super-vl:free`) used 50,309 tokens over 24 log entries and cost $0.00. Earlier real runs with `nvidia/nemotron-3-ultra-550b-a55b:free`: a good-brief run that stopped at step 1.2 used 8,126 tokens over 12 log entries, and one that halted at step 1.1 used 2,855 tokens over 8 entries; both cost $0.00. A run makes about 6–16 LLM calls, depending on how many steps it reaches and whether a step repeats: a weak idea that stops in Phase 1 or 2 uses the fewest. Each LLM entry in `decision_log.json` records the run's real `tokens` and `cost`. For a paid model, set `LLM_USD_PER_1M_TOKENS` and the cost is computed.

## Demo video

Not recorded yet.

## What our system will NOT do

- Promise income or success, in any output or marketing copy.
- Create fake reviews, testimonials, ratings, sign-ups, user counts or countdown timers.
- Pose as the founder, a customer or another brand.
- Hold, move or refund money by itself, create accounts, or store passwords or card numbers. Payments are MOCKED; refunds need founder approval.
- Publish, send or spend anything without an explicit founder `approve` at the terminal. Without a terminal, every approval is rejected.
- Work on physical goods, financial/investment/crypto products, or health or legal advice products. The brief screen stops these.
- Put core features behind a paywall. Everything here is MIT-licensed.
- Cite a source it did not retrieve. Unverifiable claims are labelled `ASSUMPTION`.

## How the project stays alive after the hackathon

- **Maintainers:** the founding team, through this repository's GitHub issues and pull requests.
- **Roadmap:** a real Phase 3 (product drafts with founder review), a test-mode payment provider behind the existing `payments.py` interface, a web UI for approvals, and more evidence sources (marketplace listings, search-trend data).
- **Community:** contributions welcome. New agents follow the `agents/<role>.py` and `prompts/<role>.md` pattern, and gate thresholds stay in `gates.py`, where changes get reviewed.
- **Funding:** none needed to run it, because it runs on free tiers and local models. Hosting a public demo would be the first cost.
