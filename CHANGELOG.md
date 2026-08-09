# Changelog

All notable changes to LocaForge are documented in this file.

## 0.3.0 — 2026-08-09

### Added

- Multi-file `.lfproj` projects, mixed-format batch import, per-file filtering,
  document statistics, and transactional batch export with original file names.
- Separate translation-model and reviewer candidates with explicit version selection.
- Operation-level translation undo with `Ctrl+Z`, including batch state, candidate,
  status, and validation restoration across project reopen.
- Field-scoped table search, comprehensive button tooltips, a Models menu, and a
  detailed project-creation summary dialog.

### Changed

- Upgraded the `.lfproj` container metadata to format version 2 while retaining
  automatic opening and migration of version 1 containers and legacy SQLite schemas.
- Extended the Ollama reviewer contract with an optional corrected translation while
  remaining compatible with issue-only reviewer responses.

## 0.2.0 — 2026-08-05

### Added

- CSV/TSV, Gettext PO, and XML import/export with format-preserving round trips.
- Translation memory, glossary management, revision history, validation filters,
  and AI-assisted review workflows.
- Reusable JSON field-mapping profiles and recent-project navigation.
- Autosave, structured logging, configurable Ollama models, and model installation.
- Windows portable build and automated packaged-application smoke testing.
- Tag-driven GitHub Releases with Python packages, Windows ZIP, and SHA-256 checksums.

### Changed

- Split desktop orchestration into focused presentation controllers and added GUI
  composition smoke tests.
- Updated the supported product scope and release documentation beyond the original
  JSON-only MVP.

## 0.1.0 — 2026-08-04

- Initial local-first JSON localization release with `.lfproj` projects, Ollama
  translation, placeholder protection, validation, and a PySide6 desktop interface.
