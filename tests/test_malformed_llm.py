"""Real models sometimes send null, a number or a bare string where a list is expected.
The pipeline must treat those as empty (or one-item) lists instead of crashing."""
import json

import pytest

from agents.common import as_list
from llm import LLMResult
from orchestrator import run_pipeline
from tests.fakes import FakeLLM, FakeSearch
from tests.test_pipeline import STRONG

LIST_FIELDS = ["queries", "supporting_claim_ids", "assumptions", "success_criteria", "components",
               "acceptance_tests", "launch_posts", "metrics_to_track", "claims"]


class ScalarListsLLM(FakeLLM):
    def __init__(self, value):
        super().__init__(STRONG)
        self.value = value

    def complete(self, system, user):
        res = super().complete(system, user)
        data = json.loads(res.text.strip("`").removeprefix("json"))
        data.update({k: self.value for k in LIST_FIELDS})
        return LLMResult(json.dumps(data), res.model, res.tokens, res.cost)


@pytest.mark.parametrize("value", [None, 0, 3.5, True, {}, "one item"])
def test_scalar_list_fields_do_not_crash(tmp_path, value):
    res = run_pipeline("briefs/good_idea.yaml", llm=ScalarListsLLM(value), search=FakeSearch(),
                       out_dir=str(tmp_path / "o"), log_path=str(tmp_path / "l.json"),
                       approval_input=lambda _: "approve", echo=lambda *_: None)
    assert res["final_outcome"] in ("go", "repeat", "pivot", "stop")


def test_as_list():
    assert as_list([1]) == [1] and as_list("a") == ["a"]
    assert as_list(None) == as_list(0) == as_list(True) == as_list({}) == as_list("  ") == []
