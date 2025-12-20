"""Story loader for YAML story specifications."""

import logging
from pathlib import Path

import yaml

from .models import Story, StoryStep

logger = logging.getLogger(__name__)


def load_story(path: Path) -> Story:
    """Load a single story from a YAML file.

    Supports both new format (steps with description/exploration_budget)
    and old format (steps as simple string list).

    Args:
        path: Path to YAML file

    Returns:
        Story object
    """
    with open(path) as f:
        data = yaml.safe_load(f)

    story_id = data.get("id", path.stem)
    persona = data.get("persona", "Generic test user")

    # Parse steps - handle both formats
    raw_steps = data.get("steps", [])
    steps = []

    for i, raw_step in enumerate(raw_steps):
        if isinstance(raw_step, dict):
            # New format with structured step
            step = StoryStep(
                id=raw_step.get("id", f"step-{i+1}"),
                description=raw_step.get("description", ""),
                exploration_budget=raw_step.get("exploration_budget", 0),
            )
        else:
            # Old format - simple string
            step = StoryStep(
                id=f"step-{i+1}",
                description=str(raw_step),
                exploration_budget=0,
            )
        steps.append(step)

    # Handle old format with goals instead of steps
    if not steps and "goals" in data:
        for i, goal in enumerate(data["goals"]):
            steps.append(
                StoryStep(
                    id=f"goal-{i+1}",
                    description=str(goal),
                    exploration_budget=1,
                )
            )

    metadata = data.get("metadata", {})
    # Also extract other metadata fields from old format
    if "description" in data:
        metadata["description"] = data["description"]
    if "timeout_seconds" in data:
        metadata["timeout_seconds"] = data["timeout_seconds"]
    if "start_url" in data:
        metadata["start_url"] = data["start_url"]

    return Story(
        id=story_id,
        persona=persona,
        steps=steps,
        metadata=metadata,
    )


def load_stories_from_directory(directory: Path) -> list[Story]:
    """Load all stories from a directory.

    Args:
        directory: Path to directory containing YAML files

    Returns:
        List of Story objects, sorted by priority (metadata.priority)
    """
    stories = []

    if not directory.exists():
        logger.warning(f"Stories directory not found: {directory}")
        return stories

    for path in directory.glob("*.yml"):
        try:
            story = load_story(path)
            stories.append(story)
            logger.info(f"Loaded story: {story.id} ({len(story.steps)} steps)")
        except Exception as e:
            logger.error(f"Failed to load story {path}: {e}")

    # Also check for .yaml extension
    for path in directory.glob("*.yaml"):
        try:
            story = load_story(path)
            stories.append(story)
            logger.info(f"Loaded story: {story.id} ({len(story.steps)} steps)")
        except Exception as e:
            logger.error(f"Failed to load story {path}: {e}")

    # Sort by priority (lower = higher priority)
    stories.sort(key=lambda s: s.metadata.get("priority", 99))

    logger.info(f"Loaded {len(stories)} stories from {directory}")
    return stories
