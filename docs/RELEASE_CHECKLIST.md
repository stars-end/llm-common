# Release Checklist

This checklist ensures that llm-common releases are consistent and reliable.

## Pre-Release

- [ ] **Create a new branch:** `release/vX.Y.Z` from `main`.
- [ ] **Update `CHANGELOG.md`:** Add a new entry for the release version, detailing all notable changes.
- [ ] **Update `pyproject.toml`:** Increment the `version` to match the new release.
- [ ] **Run tests:** Execute `make ci-lite` to ensure all tests pass.

## Release

- [ ] **Create a git tag:** `git tag vX.Y.Z -m "Release vX.Y.Z"`
- [ ] **Push the tag:** `git push origin vX.Y.Z`
- [ ] **Merge to `main`:** Open a pull request from the release branch to `main`.
- [ ] **Publish to PyPI:** Once the PR is merged, publish the package to PyPI.
