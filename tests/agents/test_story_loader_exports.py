from pathlib import Path

import yaml


def test_load_story_export(tmp_path: Path) -> None:
    from llm_common.agents import load_story

    story_path = tmp_path / "s.yml"
    story_path.write_text(
        yaml.safe_dump(
            {
                "id": "smoke",
                "persona": "investor_basic",
                "steps": ["Navigate to /"],
            }
        )
    )

    story = load_story(story_path)
    assert story.id == "smoke"
    assert story.persona == "investor_basic"
    assert len(story.steps) == 1
    assert story.steps[0]["description"] == "Navigate to /"
