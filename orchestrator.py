"""Runs the six phases, with a gate after every step.

    python orchestrator.py --brief briefs/weak_idea.yaml

Phase 1 Discover and Phase 2 Validate are working (LLM + free web search).
Phases 3-6 are STUBBED; payments and delivery are MOCKED.
Every agent action is appended to decision_log.json; outputs go to outputs/.
The run halts at the first gate that does not say GO.
"""
from __future__ import annotations

import argparse
import glob
import os
import sys
import uuid
from dataclasses import dataclass
from typing import Callable, Optional

import gates
import guardrails
import report
from agents import builder, commercial, competitor_analyst, demand_validator, experiment_designer, operator, problem_analyst, researcher, seller
from agents.common import RunContext, StepResult, load_brief
from approval import InputFn
from config import PaidModelError, load_config
from decision_log import DecisionLog
from llm import LLMClient
from search import WebSearch


@dataclass(frozen=True)
class Step:
    phase: int
    step: int
    name: str
    agent: str
    run: Callable[[RunContext, int], StepResult]

    @property
    def key(self) -> str:
        return f"phase{self.phase}_step{self.step}_{self.name}"


PHASE_NAMES = {1: "Discover", 2: "Validate", 3: "Build (STUBBED)", 4: "Commercial setup (STUBBED)",
               5: "Sell, deliver, get paid (MOCKED)", 6: "Operate and learn (STUBBED)"}

STEPS: tuple[Step, ...] = (
    Step(1, 1, "opportunities", researcher.AGENT, researcher.find_opportunities),
    Step(1, 2, "problem", problem_analyst.AGENT, problem_analyst.define_problem),
    Step(2, 1, "competitors", competitor_analyst.AGENT, competitor_analyst.scan_competitors),
    Step(2, 2, "demand", demand_validator.AGENT, demand_validator.assess_demand),
    Step(2, 3, "validation_plan", experiment_designer.AGENT, experiment_designer.design_validation_plan),
    Step(3, 1, "product_spec", builder.AGENT, builder.product_spec),
    Step(4, 1, "offer", commercial.AGENT, commercial.offer),
    Step(5, 1, "listing", commercial.AGENT, commercial.listing),
    Step(5, 2, "checkout", seller.AGENT, seller.checkout),
    Step(5, 3, "delivery", seller.AGENT, seller.delivery),
    Step(6, 1, "operate", operator.AGENT, operator.operate),
)


def run_pipeline(
    brief_path: str,
    *,
    llm,
    search,
    out_dir: str,
    log_path: str,
    approval_input: Optional[InputFn] = None,
    echo: Callable[[str], None] = print,
) -> dict:
    brief = load_brief(brief_path)
    if os.path.isdir(out_dir):  # outputs/ holds one run only: clear the previous run's phase files
        for old in glob.glob(os.path.join(out_dir, "phase*_*.md")):
            os.remove(old)
    log = DecisionLog(log_path, reset=True)
    ctx = RunContext(brief=brief, llm=llm, search=search, log=log, approval_input=approval_input)
    meta = {"run_id": uuid.uuid4().hex[:8], "brief": brief_path, "model": getattr(llm, "model_name", "unknown")}
    echo(f"Run {meta['run_id']}: '{brief.title}' with model {meta['model']}")

    violations = guardrails.check_brief(brief.raw)
    outcome = gates.STOP if violations else gates.GO
    log.record("guardrails", "screen_brief", model=None, cost=0, outcome=outcome,
               detail="; ".join(map(str, violations)) or None)
    files = [report.write_brief_screen(out_dir, violations, meta, outcome)]
    if violations:
        echo(f"STOP at brief screen: {violations[0]}")
        return {"final_outcome": gates.STOP, "halted_at": "brief_screen", "files": files, "log": log}

    halted_at, final = None, gates.GO
    for step in STEPS:
        echo(f"\n== Phase {step.phase} {PHASE_NAMES[step.phase]} / step {step.step}: {step.name}")
        attempts: list[StepResult] = []
        decisions: list[gates.GateDecision] = []
        attempt = 0
        while True:
            result = step.run(ctx, attempt)
            attempts.append(result)
            ctx.results[step.key] = result
            decision = gates.evaluate(step.key, result.metrics, attempt)
            decisions.append(decision)
            log.record("gate", f"gate:{step.key}", sources=result.sources, model=None, cost=0,
                       outcome=decision.outcome, attempt=attempt + 1, reasons=decision.reasons)
            echo(f"   gate -> {decision.outcome.upper()} ({'; '.join(decision.reasons[-2:])})")
            if decision.outcome == gates.REPEAT and attempt < gates.MAX_REPEATS:
                attempt += 1
                continue
            break
        history = ctx.results.setdefault("_gate_history", StepResult(title="", data={"lines": []}))
        history.data["lines"].append(f"{step.key}: {decisions[-1].outcome.upper()}")
        files.append(report.write_step(out_dir, step.phase, step.step, step.name, attempts, meta))
        files.append(report.write_gate(out_dir, step.phase, step.name, decisions, meta))
        if decisions[-1].outcome != gates.GO:
            halted_at, final = step.key, decisions[-1].outcome
            break

    echo(f"\nFinal: {final.upper()}" + (f" at {halted_at}" if halted_at else " (all steps passed)"))
    echo(f"Decision log: {log_path} ({len(log.entries)} entries, ${log.total_cost:.4f}, {log.total_tokens} tokens)")
    return {"final_outcome": final, "halted_at": halted_at, "files": files, "log": log}


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Run the six-phase venture pipeline on a founder brief.")
    p.add_argument("--brief", default="briefs/weak_idea.yaml",
                   help="path to a founder brief (.yaml/.yml or .md); default: %(default)s")
    args = p.parse_args(argv)
    if not os.path.isfile(args.brief):
        p.error(f"brief file not found: {args.brief}")
    try:
        cfg = load_config()
    except PaidModelError as exc:
        p.error(str(exc))
    if not sys.stdin.isatty():
        print("No interactive terminal: every founder approval will be REJECTED. "
              "Use `docker compose run --rm app` to approve steps.", file=sys.stderr)
    result = run_pipeline(
        args.brief,
        llm=LLMClient(cfg.llm),
        search=WebSearch(cfg.search_max_results, cfg.search_pause_seconds),
        out_dir=cfg.outputs_dir,
        log_path=cfg.decision_log_path,
    )
    return 0 if result["final_outcome"] in (gates.GO, gates.STOP, gates.PIVOT) else 1


if __name__ == "__main__":
    raise SystemExit(main())
