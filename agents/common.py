"""Shared types and the evidence-gathering routine used by the research agents."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from urllib.parse import urlparse

import guardrails
from approval import InputFn
from decision_log import DecisionLog
from llm import LLMClient, parse_json
from search import SearchResult, WebSearch

ASSUMPTION = "ASSUMPTION"
PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts")


def load_prompt(name: str) -> str:
    with open(os.path.join(PROMPTS_DIR, f"{name}.md"), encoding="utf-8") as fh:
        return fh.read()


@dataclass
class Brief:
    path: str
    title: str
    sections: dict[str, str]
    raw: str

    def as_text(self) -> str:
        return "\n".join(f"{k}: {v}" for k, v in self.sections.items())


YAML_FIELDS = {  # brief key -> section name used by the agents
    "idea": "Idea",
    "target_market": "Target customer",
    "problem": "Problem",
    "price": "Price idea",
    "founder_skills": "Founder skills",
    "budget_usd": "Budget (USD)",
    "time_per_week_hours": "Time per week (hours)",
    "values": "Founder values",
}


def _fmt(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value)
    return str(value).strip()


def load_brief(path: str) -> Brief:
    """Load a founder brief from YAML (.yaml/.yml) or Markdown (## headings)."""
    if not os.path.isfile(path):
        raise FileNotFoundError(f"brief not found: {path}")
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    if path.lower().endswith((".yaml", ".yml")):
        import yaml

        data = yaml.safe_load(raw) or {}
        if not isinstance(data, dict) or not str(data.get("idea") or "").strip():
            raise ValueError(f"{path}: a YAML brief needs at least an 'idea' field")
        sections = {YAML_FIELDS.get(k, k.replace("_", " ").capitalize()): _fmt(v)
                    for k, v in data.items() if v not in (None, "", [])}
        return Brief(path=path, title=_fmt(data["idea"]), sections=sections, raw=raw)
    title, sections, current = os.path.basename(path), {}, None
    for line in raw.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
        elif line.startswith("## "):
            current = line[3:].strip()
            sections[current] = ""
        elif current is not None:
            sections[current] = (sections[current] + "\n" + line).strip()
    return Brief(path=path, title=title, sections=sections, raw=raw)


@dataclass
class Claim:
    id: str
    text: str
    type: str
    source: str  # a URL returned by the search, or ASSUMPTION
    price: Optional[str] = None
    note: Optional[str] = None

    @property
    def sourced(self) -> bool:
        return self.source != ASSUMPTION


@dataclass
class StepResult:
    title: str
    summary: str = ""
    claims: list[Claim] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    body: str = ""  # extra markdown for the step output
    data: dict[str, Any] = field(default_factory=dict)
    labels: list[str] = field(default_factory=list)  # e.g. ["STUBBED"], ["MOCKED"]
    notes: list[str] = field(default_factory=list)

    @property
    def sources(self) -> list[str]:
        return sorted({c.source for c in self.claims if c.sourced})


@dataclass
class RunContext:
    brief: Brief
    llm: LLMClient
    search: WebSearch
    log: DecisionLog
    approval_input: Optional[InputFn] = None
    results: dict[str, StepResult] = field(default_factory=dict)


def domain(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def normalize_url(url: str) -> str:
    return url.strip().rstrip("/").split("#")[0]


def ask_json(ctx: RunContext, agent: str, action: str, system: str, user: str, sources: Optional[list[str]] = None) -> dict:
    """Call the LLM for a JSON object, retrying once; log every call."""
    last_err = ""
    for attempt in range(2):
        prompt = user if attempt == 0 else user + f"\n\nYour previous reply was not valid JSON ({last_err}). Reply with ONE JSON object only."
        res = ctx.llm.complete(system, prompt)
        ok = True
        try:
            data = parse_json(res.text)
        except ValueError as exc:  # json.JSONDecodeError is a ValueError
            ok, last_err, data = False, str(exc)[:80], None
        ctx.log.record(agent, action, sources=sources, model=res.model, cost=res.cost, tokens=res.tokens,
                       detail=None if ok else "reply was not valid JSON")
        if ok and isinstance(data, dict):
            return data
    return {}


def validate_claims(raw_claims: Any, allowed_types: tuple[str, ...], known_urls: set[str], prefix: str) -> tuple[list[Claim], list[str]]:
    """Turn LLM claims into Claim objects.

    A claim keeps its URL only if that exact URL came back from the web search;
    otherwise it is relabelled ASSUMPTION. Claims that break a conduct guardrail are dropped.
    """
    claims, notes = [], []
    for item in raw_claims if isinstance(raw_claims, list) else []:
        if not isinstance(item, dict):
            continue
        text = " ".join(str(item.get("text") or "").split())
        if not text:
            continue
        hits = guardrails.check_output(text)
        if hits:
            notes.append(f"dropped a claim that broke a guardrail ({hits[0].category})")
            continue
        ctype = str(item.get("type") or "other").strip().lower()
        if ctype not in allowed_types:
            ctype = "other"
        url = normalize_url(str(item.get("source_url") or item.get("source") or ""))
        note = None
        if url.upper() == ASSUMPTION or not url:
            url = ASSUMPTION
        elif url not in known_urls:
            note = "source URL was not among the search results; relabelled ASSUMPTION"
            url = ASSUMPTION
        price = item.get("price")
        claims.append(Claim(id=f"{prefix}{len(claims) + 1}", text=text, type=ctype, source=url,
                            price=str(price) if price not in (None, "", "null") else None, note=note))
    relabelled = sum(1 for c in claims if c.note)
    if relabelled:
        notes.append(f"{relabelled} claim(s) cited a URL the search never returned and were relabelled ASSUMPTION")
    return claims, notes


def claim_metrics(claims: list[Claim]) -> dict[str, Any]:
    sourced = [c for c in claims if c.sourced]
    m: dict[str, Any] = {
        "total_claims": len(claims),
        "sourced_claims": len(sourced),
        "assumptions": len(claims) - len(sourced),
        "assumption_ratio": round((len(claims) - len(sourced)) / len(claims), 2) if claims else 1.0,
        "distinct_domains": len({domain(c.source) for c in sourced}),
    }
    for c in sourced:  # type counts only include sourced claims
        m[c.type] = m.get(c.type, 0) + 1
    return m


def research_step(
    ctx: RunContext,
    *,
    agent: str,
    prompt_name: str,
    title: str,
    purpose: str,
    allowed_types: tuple[str, ...],
    claim_prefix: str,
    attempt: int,
    extra_context: str = "",
    fallback_queries: Callable[[Brief], list[str]],
) -> StepResult:
    """Plan queries -> search the web -> extract claims -> validate sources -> metrics."""
    brief_text = ctx.brief.as_text()
    previous = ctx.results.get(f"_queries_{agent}", StepResult(title="")).queries
    plan = ask_json(
        ctx, agent, "plan_search_queries", load_prompt("query_planner"),
        f"PURPOSE: {purpose}\n\nFOUNDER BRIEF:\n{brief_text}\n\n{extra_context}\n\n"
        f"ATTEMPT: {attempt + 1}. Queries already used (do not repeat them): {json.dumps(previous)}",
    )
    queries = [str(q).strip() for q in plan.get("queries", []) if str(q).strip()][:4]
    if not queries:
        queries = [q for q in fallback_queries(ctx.brief) if q not in previous][:4]
    ctx.results[f"_queries_{agent}"] = StepResult(title="", queries=previous + queries)

    results: list[SearchResult] = []
    for q in queries:
        rows = ctx.search.search(q)
        ctx.log.record(agent, "web_search", sources=[r.url for r in rows], model=None, cost=0, query=q, results=len(rows))
        results.extend(rows)
    seen, unique = set(), []
    for r in results:
        u = normalize_url(r.url)
        if u not in seen:
            seen.add(u)
            unique.append(r)
    unique = unique[:32]
    evidence = "\n".join(
        f"- URL: {normalize_url(r.url)}\n  TITLE: {r.title[:150]}\n  SNIPPET: {r.snippet[:350]}" for r in unique
    ) or "(no search results)"

    data = ask_json(
        ctx, agent, "extract_claims", load_prompt(prompt_name),
        f"FOUNDER BRIEF:\n{brief_text}\n\n{extra_context}\n\nSEARCH RESULTS:\n{evidence}",
        sources=sorted(seen),
    )
    claims, notes = validate_claims(data.get("claims"), allowed_types, seen, claim_prefix)
    summary, hits = guardrails.redact(str(data.get("summary") or "").strip())
    if hits:
        notes.append(f"guardrails removed text from the summary ({hits[0].category})")
    if not unique:
        notes.append("web search returned no results; every claim is an ASSUMPTION")
    metrics = claim_metrics(claims)
    metrics["search_results"] = len(unique)
    return StepResult(title=title, summary=summary, claims=claims, queries=queries, metrics=metrics, notes=notes)
