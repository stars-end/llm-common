from pathlib import Path

import yaml

from llm_common.agents.schemas import AgentStory


def load_story(path: Path) -> AgentStory:
    """Load a single .yml/.yaml story file into AgentStory."""
    with open(path) as f:
        data = yaml.safe_load(f)
        if not data:
            raise ValueError(f"Story file is empty: {path}")
        return AgentStory(**data)


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
            stories.append(load_story(file_path))
        except Exception as e:
            # Inline print since we don't have logger here easily without circular import
            print(f"Error loading story from {file_path}: {e}")

    return sorted(stories, key=lambda s: s.id)
