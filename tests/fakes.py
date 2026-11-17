"""Test doubles. Used only by the offline smoke tests in tests/; never by a real run."""
import json

from llm import LLMResult
from search import SearchResult


class FakeSearch:
    def __init__(self, urls_per_query=4, domain_pool=("a.com", "b.org", "c.net", "d.io")):
        self.calls = []
        self.urls_per_query = urls_per_query
        self.domain_pool = domain_pool

    def search(self, query):
        self.calls.append(query)
        n = len(self.calls)
        return [SearchResult(title=f"t{n}-{i}", url=f"https://{self.domain_pool[i % len(self.domain_pool)]}/q{n}/r{i}",
                             snippet="snippet", query=query) for i in range(self.urls_per_query)]


class FakeLLM:
    """Answers by prompt type. `claims_by_agent` maps a prompt heading word to a list of
    (type, url_or_None) tuples; None means 'cite the first search result URL n'."""
    model_name = "fake-model"

    def __init__(self, claims_by_agent=None, landing_copy="Plan your week. Join the waitlist."):
        self.claims_by_agent = claims_by_agent or {}
        self.landing_copy = landing_copy
        self.calls = 0

    def _urls(self, user):
        return [line.split("URL: ", 1)[1].strip() for line in user.splitlines() if "URL: " in line]

    def complete(self, system, user):
        self.calls += 1
        head = system.splitlines()[0]
        if "Query planner" in head:
            data = {"queries": [f"q{self.calls}a", f"q{self.calls}b"]}
        elif "Problem analyst" in head:
            ids = [line.split('"id": "')[1].split('"')[0] for line in user.splitlines() if '"id": "' in line]
            data = {"target_customer": "office workers", "problem_statement": "Low weekday motivation [O1].",
                    "supporting_claim_ids": ids[:4], "assumptions": ["they would pay"]}
        elif "Experiment designer" in head:
            data = {"landing_page_copy": self.landing_copy, "experiment": "Waitlist for 14 days.",
                    "success_criteria": ["30 sign-ups from 500 visitors"]}
        else:
            key = next(k for k in ("Researcher", "Competitor", "Demand") if k in head)
            urls = self._urls(user)
            claims = []
            for i, (ctype, url) in enumerate(self.claims_by_agent.get(key, [])):
                src = url if url else (urls[i % len(urls)] if urls else "ASSUMPTION")
                claims.append({"text": f"claim {i} about {ctype}", "type": ctype, "source_url": src,
                               "price": "$12" if ctype == "competitor" else None})
            data = {"claims": claims, "summary": f"{key} summary."}
        return LLMResult(text="```json\n" + json.dumps(data) + "\n```", model=self.model_name, tokens=100, cost=0.0)
