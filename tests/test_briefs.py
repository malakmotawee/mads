import pytest

import guardrails
from agents.common import load_brief
from orchestrator import main


@pytest.mark.parametrize("path", ["briefs/weak_idea.yaml", "briefs/good_idea.yaml"])
def test_sample_briefs_load_and_pass_the_screen(path):
    b = load_brief(path)
    assert b.title and b.sections["Idea"] == b.title and "Target customer" in b.sections
    assert guardrails.check_brief(b.raw) == []


def test_yaml_lists_are_flattened():
    assert load_brief("briefs/good_idea.yaml").sections["Founder skills"] == "Notion, event planning, student club leadership"


def test_yaml_brief_needs_an_idea(tmp_path):
    f = tmp_path / "b.yaml"
    f.write_text("budget_usd: 0\n")
    with pytest.raises(ValueError):
        load_brief(str(f))


def test_markdown_briefs_still_load(tmp_path):
    f = tmp_path / "b.md"
    f.write_text("# My idea\n\n## Idea\nA planner template\n\n## Target customer\nTeachers\n")
    assert load_brief(str(f)).sections == {"Idea": "A planner template", "Target customer": "Teachers"}


def test_cli_rejects_a_missing_brief():
    with pytest.raises(SystemExit):
        main(["--brief", "briefs/does_not_exist.yaml"])
