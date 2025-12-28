"""
Tests for the Unified Verification Framework.
"""

from pathlib import Path

import pytest

from llm_common.verification import (
    ArtifactManager,
    ReportGenerator,
    StoryCategory,
    StoryResult,
    StoryStatus,
    VerificationConfig,
    VerificationReport,
    VerificationStory,
)
from llm_common.verification.stories.rag_stories import get_rag_stories
from llm_common.verification.stories.user_stories import get_user_stories


class TestVerificationStory:
    """Tests for VerificationStory dataclass."""

    def test_story_creation(self):
        """Test creating a verification story."""
        story = VerificationStory(
            id="test_01",
            name="Test Story",
            category=StoryCategory.RAG_PIPELINE,
            phase=1,
        )
        assert story.id == "test_01"
        assert story.name == "Test Story"
        assert story.category == StoryCategory.RAG_PIPELINE
        assert story.phase == 1

    def test_screenshot_name(self):
        """Test screenshot name generation."""
        story = VerificationStory(
            id="rag_05_vector",
            name="Vector Store",
            category=StoryCategory.RAG_PIPELINE,
            phase=5,
        )
        assert story.screenshot_name == "rag_05_vector.png"

    def test_requires_browser_default(self):
        """Test default browser requirement."""
        story = VerificationStory(
            id="test",
            name="Test",
            category=StoryCategory.USER_STORY,
            phase=0,
        )
        assert story.requires_browser is False
        assert story.requires_llm is False


class TestStoryResult:
    """Tests for StoryResult dataclass."""

    def test_result_creation(self):
        """Test creating a story result."""
        story = VerificationStory(
            id="test",
            name="Test",
            category=StoryCategory.RAG_PIPELINE,
            phase=0,
        )
        result = StoryResult(
            story=story,
            status=StoryStatus.PASSED,
            duration_seconds=1.5,
        )
        assert result.passed is True
        assert result.duration_seconds == 1.5

    def test_failed_result(self):
        """Test failed result properties."""
        story = VerificationStory(
            id="test",
            name="Test",
            category=StoryCategory.USER_STORY,
            phase=1,
        )
        result = StoryResult(
            story=story,
            status=StoryStatus.FAILED,
            error="Connection timeout",
        )
        assert result.passed is False
        assert result.error == "Connection timeout"


class TestVerificationConfig:
    """Tests for VerificationConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = VerificationConfig()
        assert config.artifacts_dir == "artifacts/verification"
        assert config.enable_screenshots is True
        assert config.enable_glm_validation is True

    def test_run_dir(self):
        """Test run directory path generation."""
        config = VerificationConfig(run_id="test-run-123")
        assert config.run_dir == Path("artifacts/verification/test-run-123")
        assert config.screenshots_dir == Path("artifacts/verification/test-run-123/screenshots")


class TestVerificationReport:
    """Tests for VerificationReport."""

    def test_empty_report(self):
        """Test empty report properties."""
        config = VerificationConfig()
        report = VerificationReport(config=config)
        assert report.total == 0
        assert report.passed == 0
        assert report.success_rate == 0.0

    def test_report_with_results(self):
        """Test report with mixed results."""
        config = VerificationConfig()
        report = VerificationReport(config=config)

        for i, status in enumerate([StoryStatus.PASSED, StoryStatus.PASSED, StoryStatus.FAILED]):
            story = VerificationStory(
                id=f"test_{i}",
                name=f"Test {i}",
                category=StoryCategory.RAG_PIPELINE,
                phase=i,
            )
            report.results.append(StoryResult(story=story, status=status))

        assert report.total == 3
        assert report.passed == 2
        assert report.failed == 1
        assert report.success_rate == pytest.approx(66.67, rel=0.1)


class TestRagStories:
    """Tests for RAG pipeline stories."""

    def test_get_rag_stories(self):
        """Test getting all RAG stories."""
        stories = get_rag_stories()
        assert len(stories) == 12

    def test_rag_story_phases(self):
        """Test RAG stories have correct phases."""
        stories = get_rag_stories()
        phases = [s.phase for s in stories]
        assert phases == list(range(12))

    def test_discovery_story(self):
        """Test discovery story properties."""
        stories = get_rag_stories()
        discovery = next(s for s in stories if "discovery" in s.id)
        assert discovery.requires_llm is True
        assert discovery.llm_model == "glm-4.7"


class TestUserStories:
    """Tests for user stories."""

    def test_get_user_stories(self):
        """Test getting all user stories."""
        stories = get_user_stories()
        assert len(stories) == 8

    def test_user_story_categories(self):
        """Test all user stories have correct category."""
        stories = get_user_stories()
        for story in stories:
            assert story.category == StoryCategory.USER_STORY

    def test_chat_story(self):
        """Test deep chat story properties."""
        stories = get_user_stories()
        chat = next(s for s in stories if "chat" in s.id)
        assert chat.requires_browser is True
        assert chat.requires_llm is True


class TestReportGenerator:
    """Tests for ReportGenerator."""

    def test_generate_markdown(self, tmp_path):
        """Test Markdown report generation."""
        config = VerificationConfig(
            run_id="test-run",
            artifacts_dir=str(tmp_path),
        )
        report = VerificationReport(
            config=config,
            start_time="2025-01-01T00:00:00",
            end_time="2025-01-01T00:01:00",
        )

        generator = ReportGenerator(report)
        md_content = generator.generate_markdown()

        assert "# Verification Report" in md_content
        assert "test-run" in md_content

    def test_generate_json(self, tmp_path):
        """Test JSON summary generation."""
        config = VerificationConfig(
            run_id="test-run",
            artifacts_dir=str(tmp_path),
        )
        report = VerificationReport(config=config)

        generator = ReportGenerator(report)
        json_data = generator.generate_json()

        assert json_data["run_id"] == "test-run"
        assert "summary" in json_data


class TestArtifactManager:
    """Tests for ArtifactManager."""

    def test_create_run_dir(self, tmp_path):
        """Test run directory creation."""
        manager = ArtifactManager(base_dir=str(tmp_path))
        run_dir = manager.create_run_dir("test-run")

        assert run_dir.exists()
        assert (run_dir / "screenshots").exists()
        assert (run_dir / "logs").exists()

    def test_screenshot_path(self, tmp_path):
        """Test screenshot path generation."""
        manager = ArtifactManager(base_dir=str(tmp_path))
        run_dir = tmp_path / "verify-test"

        path = manager.screenshot_path(run_dir, "rag_01_discovery")
        assert path == run_dir / "screenshots" / "rag_01_discovery.png"
