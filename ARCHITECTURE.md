# Architecture

## Overview

`orchestrator.py` loads a founder brief (YAML or Markdown), screens it with `guardrails.py`, and then runs eleven steps across six phases. After every step, `gates.py` turns metrics computed in code into **go / repeat / pivot / stop**, and the run halts at the first gate that is not GO. Phases 1 and 2 are real agents: an OpenAI-compatible LLM (OpenRouter `openai/gpt-oss-120b:free`, or local Ollama `gpt-oss:20b`) plus free web search through `ddgs`. Phases 3–6 are **STUBBED**, and payments and delivery are **MOCKED**. Every outward-facing action goes through `approval.py`. Every agent action is appended to `decision_log.json`, and every step and gate is written to `outputs/`.

```mermaid
flowchart TD
    B[Founder brief<br/>briefs/*.yaml] --> S{Brief screen<br/>guardrails.py}
    S -- excluded product / conduct --> X[STOP]
    S -- pass --> P11[1.1 Opportunities<br/>researcher]
    P11 --> G11{gate}
    G11 -- go --> P12[1.2 Problem<br/>problem_analyst]
    P12 --> G12{gate}
    G12 -- go --> P21[2.1 Competitors<br/>competitor_analyst]
    P21 --> G21{gate}
    G21 -- go --> P22[2.2 Demand<br/>demand_validator]
    P22 --> G22{gate}
    G22 -- go --> P23[2.3 Validation plan<br/>experiment_designer]
    P23 --> A1[[founder approval:<br/>publish smoke test]]
    A1 --> G23{gate}
    G23 -- go --> P3[3 Build STUBBED]
    P3 --> P4[4 Offer + listing STUBBED<br/>approval to publish]
    P4 --> P5[5 Checkout + delivery MOCKED<br/>approval to publish]
    P5 --> P6[6 Operate STUBBED]
    G11 & G12 & G21 & G22 & G23 -- repeat --> R[re-run step once<br/>with new queries]
    G11 & G12 & G21 & G22 & G23 -- pivot / stop --> H[halt + recommendation]
```

Every gate (including the stub gates after steps 3–6) writes `outputs/phase<N>_gate_<name>.md` and a `gate` entry in `decision_log.json`.

## Phases

### Phase 1: Discover (Working)

**Step 1.1, Opportunities.** Agent: `agents/researcher.py`, prompt `prompts/researcher.md`.
- *Tools:* LLM query planner (`prompts/query_planner.md`) and `search.WebSearch` (ddgs, no key).
- *Method:* the LLM writes 3–4 neutral and sceptical queries. Each query is searched, and the results are de-duplicated (up to 32). The LLM extracts up to 12 claims typed `pain`, `workaround`, `trend` or `other`, each with a `source_url`. `agents/common.validate_claims` keeps a URL **only if the search actually returned it**; any other URL becomes `ASSUMPTION` and is noted. Claims that break a conduct guardrail are dropped.
- *Output:* `outputs/phase1_step1_opportunities.md`, a claims table with sources and metrics (`sourced_claims`, `distinct_domains`, `assumption_ratio`, `pain`, ...).

**Step 1.2, Problem.** Agent: `agents/problem_analyst.py`.
- *Method:* no new search. The LLM writes a target customer and a problem statement that cite step 1.1 claim IDs, and lists open assumptions. The code keeps only claim IDs that exist, and counts only the sourced ones as support.
- *Output:* `outputs/phase1_step2_problem.md`. Every unsupported belief is listed as `ASSUMPTION:`.

### Phase 2: Validate (Working; publishing STUBBED)

**Step 2.1, Competitors.** Agent: `agents/competitor_analyst.py`.
- *Method:* the same search-and-extract loop. Claims are typed `competitor`, `free_alternative`, `price_point` or `other`. A **paid price point** counts only if the claim is sourced and a currency amount is visible in it.
- *Output:* `outputs/phase2_step1_competitors.md`.

**Step 2.2, Demand.** Agent: `agents/demand_validator.py`.
- *Method:* searches for evidence of paying or refusing to pay. Claims are typed `wtp_positive`, `wtp_negative`, `demand_signal` or `other`. The prompt says general interest is not willingness to pay. The code counts the distinct domains behind the positive signals.
- *Output:* `outputs/phase2_step2_demand.md`.

**Step 2.3, Validation plan.** Agent: `agents/experiment_designer.py`.
- *Method:* the LLM drafts landing-page copy, an experiment and success criteria fixed before the test runs. The copy is screened with the stricter marketing rules: no testimonials, ratings, user counts, scarcity or income claims. Clean copy is shown to the founder with `approval.request_approval`. Only after `approve` does `publish_landing_page` run, and it is **STUBBED** (nothing goes online).
- *Output:* `outputs/phase2_step3_validation_plan.md`.

### Phase 3: Build (STUBBED)
`agents/builder.py` restates the validated problem and plan as a spec outline. It calls no LLM and builds nothing. Output: `phase3_step1_product_spec.md`.

### Phase 4: Commercial setup (STUBBED)
`agents/commercial.py`. Step 4.1 restates the founder's price and the sourced competitor prices. Step 4.2 puts a listing in front of the founder, and `publish_listing` (STUBBED) runs only after approval.

### Phase 5: Sell, deliver, get paid (MOCKED)
`agents/seller.py`. Step 5.1 creates a **MOCKED** checkout through `payments.MockPaymentProvider.create_checkout`, which requires an approval for `publish_checkout:<product>`. Step 5.2 confirms that delivery is wired to payment webhooks. The pipeline never simulates sales. The full mocked flow runs in `payment_test.py` (see Sale to cash).

### Phase 6: Operate and learn (STUBBED)
`agents/operator.py` describes the planned review loop (reconcile weekly, compare results with the Phase 2 success criteria, feed them back into the gates). No live data is connected.

## Gates

Thresholds live in `gates.THRESHOLDS`. They are fixed before any run and are read-only (`MappingProxyType`). Metrics are computed in code from validated claims, so the LLM cannot grade its own evidence. `MAX_REPEATS = 1`.

| Gate | GO when | REPEAT | PIVOT | STOP |
|---|---|---|---|---|
| Brief screen | no guardrail hit | — | — | excluded product or conduct rule hit |
| 1.1 Opportunities | ≥6 sourced claims, ≥3 domains, ≥3 pain signals, assumption ratio ≤0.4 | evidence too thin, first attempt | volume met but only 1–2 pain signals | volume met with 0 pain signals; or still thin after the repeat |
| 1.2 Problem | statement backed by ≥3 sourced claims, ≤4 open assumptions | not met, first attempt | — | still not met after the repeat |
| 2.1 Competitors | ≥5 sourced claims, ≥3 domains, ≥1 sourced paid price point | not met, first attempt | — | ≥5 sourced free alternatives and 0 paid price points (saturated); or still thin after the repeat |
| 2.2 Demand | ≥3 sourced willingness-to-pay signals from ≥3 domains, and more positive than negative | not met, first attempt | — | ≥2 negative signals and ≥2× as many negative as positive; or still thin after the repeat |
| 2.3 Validation plan | 0 guardrail violations and founder approved | rejected or violation, first attempt | — | still rejected / violating after the repeat |
| 3.1–6.1 (stubs) | artifact produced, plus founder approval where the step publishes | not met, first attempt | — | still not met after the repeat |

```mermaid
stateDiagram-v2
    [*] --> RunStep
    RunStep --> Evaluate
    Evaluate --> GO: all thresholds met
    Evaluate --> REPEAT: weak, attempt 1
    REPEAT --> RunStep: new queries
    Evaluate --> PIVOT: evidence points elsewhere
    Evaluate --> STOP: strong negative evidence
    Evaluate --> STOP: still weak after repeat
    GO --> [*]: next step
    PIVOT --> [*]: halt, rework brief
    STOP --> [*]: halt
```

**When the system recommends STOP on weak evidence:** any evidence gate that is still below its thresholds after one repeat recommends STOP, rather than going forward on hope. It also recommends STOP straight away on strong negative evidence: a market full of free substitutes with no sourced paid price, or sourced refusals to pay that outweigh the evidence of paying. A STOP writes the reasons, the metrics and the thresholds to `outputs/phase<N>_gate_<name>.md`.

## Sale to cash

All of this is **MOCKED** (`payments.py`, `delivery.py`, `refunds.py`, `reconcile.py`). No payment provider, sandbox or real money is involved. Run it with `python payment_test.py`, which writes `outputs/payment_test_log.md`.

```mermaid
sequenceDiagram
    participant F as Founder
    participant P as MockPaymentProvider
    participant W as WebhookHandler
    participant D as DeliveryService
    participant R as refunds.refund_order
    F->>P: approve publish_checkout
    P-->>F: mock://checkout/cs_x
    Note over P: buyer pays (test harness only)
    P->>W: payment_succeeded evt_1
    W->>D: grant_access(order) (once per order)
    P->>W: payment_succeeded evt_1 (duplicate)
    W-->>P: duplicate_event_ignored
    F->>R: approve refund:order
    R->>D: revoke_access(order)
    P->>P: payout (net of fees and refunds)
    Note over P,D: reconcile(): orders, payments, fees, refunds, grants, payouts
```

- **Payment triggers delivery:** `WebhookHandler.handle` grants access only on `payment_succeeded`, and only for an order that is still `pending`.
- **Idempotency:** processed event IDs are stored, so a repeated event returns `duplicate_event_ignored`. `DeliveryService.grant_access` returns the existing grant for an order, so there is never a second delivery.
- **A refund revokes access:** `refund_order` needs a founder approval for `refund:<order_id>`. It marks the order and payment refunded and revokes the grant. The system never refunds by itself.
- **Reconciliation:** `reconcile()` checks every order against its payment (amount, and fee against the MOCKED fee schedule of 2.9% + $0.30). It checks that paid orders are delivered, refunded orders are revoked, nothing was delivered twice or without payment, and payouts equal gross − fees − refunds.
- No names, emails, passwords or card numbers are stored. Buyers are opaque references.

## Data flow

```mermaid
flowchart LR
    brief[briefs/*.yaml] --> orch[orchestrator.py]
    env[.env: LLM_* / OLLAMA_*] --> cfg[config.py] --> llm[llm.py]
    orch --> agents[agents/*.py]
    prompts[prompts/*.md] --> agents
    agents -- queries --> search[search.py / ddgs] -- URLs + snippets --> agents
    agents -- prompts --> llm -- JSON --> agents
    agents --> val[validate_claims:<br/>URL must be in results]
    val --> gates[gates.py]
    agents --> appr[approval.py] --> founder((founder at terminal))
    agents & gates & appr --> log[decision_log.json]
    agents & gates --> out[outputs/phaseN_*.md]
```

Each `decision_log.json` entry has `timestamp`, `agent`, `action`, `sources`, `model`, `cost` and `approved_by`, plus optional `outcome`, `tokens`, `query` and `detail`. `approved_by` is `"founder"` only when the founder typed `approve`. The log and `outputs/` are reset at the start of each run, so they always describe a single run.

## Built vs. stubbed

| Component | Status |
|---|---|
| Brief loader (YAML/Markdown), config, LLM client with Ollama fallback and auto-pull | Built |
| Web search (ddgs), claim validation, metrics | Built |
| Phase 1 and Phase 2 agents and prompts | Built |
| Gates with fixed thresholds | Built |
| Founder approval (CLI), guardrails, decision log | Built |
| Landing page, listing publishing | STUBBED |
| Phase 3 build, Phase 4 offer, Phase 6 operate | STUBBED |
| Payments, delivery, refunds, payouts, reconciliation | MOCKED |

## Roadmap

1. Phase 3: draft the product (for example, a template kit) with the LLM, with founder review before anything is shared.
2. Replace `MockPaymentProvider` with a test-mode provider behind the same interface, keeping founder approval for checkout and refunds.
3. More evidence sources (marketplace listings, trend data), with the same "URL must be retrieved" rule.
4. A small web UI for approvals as well as the CLI.
5. Calibrate gate thresholds against past runs, and publish the changes in `gates.py` with their reasons.
