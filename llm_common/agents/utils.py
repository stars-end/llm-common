from pathlib import Path
from typing import Any

import yaml

from llm_common.agents.schemas import AgentStory


def _normalize_story_data(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize story YAML data to AgentStory format.

    Handles:
    - Converting 'goals' to 'steps' (legacy format)
    - Ensuring required fields exist

    Args:
        data: Raw YAML data

    Returns:
        Normalized data for AgentStory
    """
    normalized = dict(data)

    # Map 'goals' to 'steps' if needed (legacy format)
    if "goals" in normalized and "steps" not in normalized:
        goals = normalized.pop("goals")
        # Convert goal strings to step dicts
        steps = []
        for i, goal in enumerate(goals):
            if isinstance(goal, str):
                steps.append(
                    {
                        "id": f"step-{i + 1}",
                        "description": goal,
                        "validation_criteria": [],
                    }
                )
            elif isinstance(goal, dict):
                if "id" not in goal:
                    goal = {**goal, "id": f"step-{i + 1}"}
                if "validation_criteria" not in goal:
                    goal = {**goal, "validation_criteria": []}
                steps.append(goal)
        normalized["steps"] = steps

    # Map 'description' to metadata if it exists
    if "description" in normalized and "metadata" not in normalized:
        normalized["metadata"] = {"description": normalized.pop("description")}
    elif "description" in normalized:
        if "metadata" not in normalized:
            normalized["metadata"] = {}
        normalized["metadata"]["description"] = normalized.pop("description")

    # Handle other legacy metadata fields
    metadata = normalized.setdefault("metadata", {})
    if "timeout_seconds" in normalized:
        metadata["timeout_seconds"] = normalized.pop("timeout_seconds")
    if "start_url" in normalized:
        metadata["start_url"] = normalized.pop("start_url")

    return normalized


def load_story(file_path: Path) -> AgentStory:
    """Load a single story from a YAML file.

    Args:
        file_path: Path to YAML file

    Returns:
        AgentStory object

    Raises:
        ValueError: If file doesn't exist or parsing fails
    """
    if not file_path.exists():
        raise ValueError(f"Story file not found: {file_path}")

    try:
        with open(file_path) as f:
            data = yaml.safe_load(f)

        if not data:
            raise ValueError(f"Empty story file: {file_path}")

        # Set default id from filename if not specified
        if "id" not in data:
            data["id"] = file_path.stem

        # Normalize data for AgentStory
        normalized = _normalize_story_data(data)

        return AgentStory(**normalized)
    except Exception as e:
        raise ValueError(f"Error loading story from {file_path}: {e}") from e


def load_stories_from_directory(directory: Path) -> list[AgentStory]:
    """Load all .yml/.yaml stories from a directory.

    Args:
        directory: Path to directory containing story YAML files

    Returns:
        List of AgentStory objects
    """
    stories = []
    if not directory.exists():
        return stories

    for file_path in directory.glob("*.y*ml"):
        try:
            story = load_story(file_path)
            stories.append(story)
        except Exception as e:
            # Inline print since we don't have logger here easily without circular import
            print(f"Error loading story from {file_path}: {e}")

    return sorted(stories, key=lambda s: s.id)
