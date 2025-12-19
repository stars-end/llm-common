import yaml
from pathlib import Path
from typing import List
from llm_common.agents.schemas import AgentStory

def load_stories_from_directory(directory: Path) -> List[AgentStory]:
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
            with open(file_path, "r") as f:
                data = yaml.safe_load(f)
                if not data:
                    continue
                # Map YAML keys to AgentStory fields (handling slight variations if needed)
                stories.append(AgentStory(**data))
        except Exception as e:
            # Inline print since we don't have logger here easily without circular import
            print(f"Error loading story from {file_path}: {e}")
            
    return sorted(stories, key=lambda s: s.id)
