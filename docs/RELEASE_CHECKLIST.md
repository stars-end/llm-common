# llm-common Release Process

This document outlines the process for releasing a new version of the `llm-common` library. Following these steps ensures that releases are consistent, well-documented, and easy for downstream consumers to use.

## Versioning

This project adheres to [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

- **MAJOR** version for incompatible API changes.
- **MINOR** version for adding functionality in a backward-compatible manner.
- **PATCH** version for backward-compatible bug fixes.

## Release Steps

### 1. Pre-Release

- [ ] **Create a release branch:** From `master`, create a new branch named `release/vX.Y.Z` (e.g., `release/v0.8.0`).
- [ ] **Update `CHANGELOG.md`:** Add a new entry under the `[Unreleased]` section. Detail all notable changes since the last release, categorized by `Added`, `Changed`, `Fixed`, `Removed`.
- [ ] **Update `pyproject.toml`:** Set the `version` to the new release number.
- [ ] **Run tests:** Execute `make ci-lite` to ensure all tests, linting, and type checks pass.

### 2. Tagging and Release

- [ ] **Create a Git Tag:** The tag version **must** match the version in `pyproject.toml`. Create an annotated tag:
  ```bash
  git tag vX.Y.Z -m "Release vX.Y.Z"
  ```
- [ ] **Push the Tag:**
  ```bash
  git push origin vX.Y.Z
  ```
- [ ] **Merge to `master`:** Open a pull request from the release branch to `master`. Ensure it passes all CI checks and get it reviewed and approved.
- [ ] **Publish to PyPI:** Once the PR is merged into `master`, the new version will be automatically published via CI/CD.

## Pinning for Downstream Consumers

Downstream repositories should pin to a specific Git tag to ensure build stability. Pinning to a commit hash is discouraged as it makes it difficult to track versions.

To pin to a tag in your `pyproject.toml`:

```toml
[tool.poetry.dependencies]
llm-common = {git = "ssh://git@github.com/stars-end/llm-common.git", tag = "v0.7.3"}
```

Or in a `requirements.txt` file:

```
git+ssh://git@github.com/stars-end/llm-common.git@v0.7.3#egg=llm-common
```
