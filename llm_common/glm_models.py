"""Standardized GLM model configuration for z.ai Coding Plan.

This module provides canonical model names to use across all repos.
Import from here instead of hardcoding model strings.

Usage:
    from llm_common.glm_models import GLMModels

    client = ZaiClient(config)
    response = await client.chat_completion(messages, model=GLMModels.FLAGSHIP)
"""


class GLMModels:
    """Standardized GLM model names for z.ai Coding Plan.

    All models use the Coding endpoint: https://api.z.ai/api/coding/paas/v4

    Use these constants instead of hardcoded strings to:
    - Ensure consistency across repos
    - Enable easy upgrades when new models release
    - Avoid typos and 429 errors from wrong model names
    """

    # ==========================================================================
    # Primary Models (use these)
    # ==========================================================================

    # Flagship reasoning model - 90%+ of use cases
    # Best for: Analysis, planning, code generation, complex reasoning
    FLAGSHIP = "glm-4.7"

    # Vision/multimodal model - screenshots, images, diagrams
    # Best for: UI testing, image analysis, document OCR
    VISION = "glm-4.6v"

    # Optional fallback vision model for extraction-heavy tasks.
    # Note: availability depends on the provider plan; UISmokeAgent will retry with VISION on failure.
    VISION_FALLBACK = "glm-4.5v"
    VISION_OCR = VISION_FALLBACK

    # Lightweight/flash model - fast, non-reasoning
    # Best for: Simple extraction, classification, quick responses
    FLASH = "glm-4.5"

    # ==========================================================================
    # Semantic Aliases (for clarity in specific contexts)
    # ==========================================================================

    DEFAULT = FLAGSHIP  # Default for most use cases
    REASONING = FLAGSHIP  # Explicit reasoning tasks
    MULTIMODAL = VISION  # Alias for vision
    FAST = FLASH  # Speed-critical paths

    # ==========================================================================
    # Configuration
    # ==========================================================================

    # The Coding Plan endpoint (NOT the general endpoint)
    CODING_ENDPOINT = "https://api.z.ai/api/coding/paas/v4"


# Convenience exports
DEFAULT_MODEL = GLMModels.FLAGSHIP
VISION_MODEL = GLMModels.VISION
FLASH_MODEL = GLMModels.FLASH


__all__ = [
    "GLMModels",
    "DEFAULT_MODEL",
    "VISION_MODEL",
    "FLASH_MODEL",
]
