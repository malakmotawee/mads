"""Writes step and gate outputs as Markdown: outputs/phase<N>_step<M>_<name>.md and phase<N>_gate_<name>.md."""
from __future__ import annotations

import os
from typing import Optional

from agents.common import StepResult
from gates import GateDecision


def step_path(out_dir: str, phase: int, step: int, name: str) -> str:
    return os.path.join(out_dir, f"phase{phase}_step{step}_{name}.md")


def gate_path(out_dir: str, phase: int, name: str) -> str:
    return os.path.join(out_dir, f"phase{phase}_gate_{name}.md")


def _write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text.rstrip() + "\n")


def render_step(phase: int, step: int, name: str, attempts: list[StepResult], run_meta: dict) -> str:
    latest = attempts[-1]
    labels = f" [{', '.join(latest.labels)}]" if latest.labels else ""
    out = [f"# Phase {phase}, step {step}: {latest.title}{labels}", "",
           f"Run {run_meta['run_id']} - brief `{run_meta['brief']}` - model `{run_meta['model']}` - {len(attempts)} attempt(s).",
           "Every claim below cites a URL returned by the web search, or is labelled ASSUMPTION.", ""]
    for i, res in enumerate(reversed(attempts)):
        n = len(attempts) - i
        out.append(f"## Attempt {n}" + (" (latest)" if i == 0 else ""))
        if res.summary:
            out += ["", "**Summary:** " + res.summary]
        if res.queries:
            out += ["", "**Search queries:** " + "; ".join(f"`{q}`" for q in res.queries)]
        if res.claims:
            out += ["", "| ID | Type | Claim | Source |", "|---|---|---|---|"]
            for c in res.claims:
                text = c.text.replace("|", "/") + (f" (price: {c.price})" if c.price else "")
                src = c.source if c.sourced else "ASSUMPTION" + (f" ({c.note})" if c.note else "")
                out.append(f"| {c.id} | {c.type} | {text} | {src} |")
        elif not res.body:
            out += ["", "_No claims extracted._"]
        if res.body:
            out += ["", res.body]
        if res.notes:
            out += ["", "**Notes:**"] + [f"- {n_}" for n_ in res.notes]
        out += ["", "**Metrics:** " + ", ".join(f"{k}={v}" for k, v in res.metrics.items()), ""]
    return "\n".join(out)


def render_gate(name: str, decisions: list[GateDecision], run_meta: dict) -> str:
    final = decisions[-1]
    out = [f"# Gate: {final.step_key}", "",
           f"**Outcome: {final.outcome.upper()}**" + (" (MOCKED step)" if final.stubbed else ""), "",
           final.recommendation, "",
           f"Run {run_meta['run_id']}. Thresholds are fixed in `gates.py` before the run.", ""]
    for d in decisions:
        out += [f"## Attempt {d.attempt + 1}: {d.outcome.upper()}", ""]
        out += [f"- {r}" for r in d.reasons]
        if d.thresholds:
            out += ["", "Thresholds: " + ", ".join(f"{k}={v}" for k, v in d.thresholds.items())]
        out += ["", "Metrics: " + ", ".join(f"{k}={v}" for k, v in d.metrics.items()), ""]
    return "\n".join(out)


def write_step(out_dir: str, phase: int, step: int, name: str, attempts: list[StepResult], meta: dict) -> str:
    path = step_path(out_dir, phase, step, name)
    _write(path, render_step(phase, step, name, attempts, meta))
    return path


def write_gate(out_dir: str, phase: int, name: str, decisions: list[GateDecision], meta: dict) -> str:
    path = gate_path(out_dir, phase, name)
    _write(path, render_gate(name, decisions, meta))
    return path


def write_brief_screen(out_dir: str, violations: list, meta: dict, outcome: str) -> str:
    path = gate_path(out_dir, 1, "brief_screen")
    lines = ["# Gate: brief screen (guardrails)", "", f"**Outcome: {outcome.upper()}**", "",
             f"Run {meta['run_id']} - brief `{meta['brief']}`.", ""]
    if violations:
        lines += ["The brief breaks the project's limits, so no agent runs:", ""] + [f"- {v}" for v in violations]
    else:
        lines += ["- PASS no excluded product category (physical, financial/crypto, health/legal advice)",
                  "- PASS no fake reviews, income promises, fake scarcity or impersonation"]
    _write(path, "\n".join(lines))
    return path
