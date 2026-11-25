import json
from pathlib import Path

from parampara.domain.generated import SkillGraph

FIXTURE = Path(__file__).parents[3] / "contracts" / "fixtures" / "skill-graph.terminal-wiring.json"


def test_terminal_wiring_fixture_parses_into_generated_model() -> None:
    graph = SkillGraph.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))
    assert [s.id for s in graph.steps] == ["s1", "s2", "s3", "s4", "s5", "s6"]
