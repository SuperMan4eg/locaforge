[English](CHANGELOG.md) | [Русский](CHANGELOG.ru.md)

# Changelog

All notable changes to LocaForge are documented in this file.

## Unreleased

## 0.4.2 — 2026-08-11

- Application workflows are now split into focused services for projects, documents,
  translation, review, terminology, validation, reporting, and model configuration.
- The main window is now a composition surface backed by dedicated controllers, action bundles,
  and widget builders, reducing UI coupling while preserving existing behavior.
- Architecture documentation now records the orchestration boundaries between the stateful
  workspace facade, application services, and presentation components.
- The refactored architecture is covered by expanded unit and smoke tests; the release baseline
  passes 551 tests together with strict type checking and linting.

## 0.4.1 — 2026-08-10

- Project containers now verify ZIP members and SQLite integrity before opening or saving.
- Manual saves retain three generations of automatic backups while keeping `.lfproj.bak` as
  the newest recovery copy.
- Windows CI now exercises a complete create, edit, save, reopen, and export lifecycle through
  the packaged executable in addition to launching its UI.
- SQLite repositories now close every short-lived connection deterministically, preventing locked
  working databases during cleanup and packaged lifecycle checks.
- The Logs panel can copy a privacy-preserving diagnostic report containing runtime versions and
  aggregate project state, never project names, paths, strings, translations, prompts, or logs.
- Unhandled failures receive a short incident ID shared by the local traceback, safe error dialog,
  and diagnostic report; packaged self-tests suppress dialogs so failures cannot stall CI.
- Python wheel builds no longer duplicate bundled localization resources under recent Hatchling
  versions; wheel and source archives are verified with the 0.4.1 release artifacts.

## 0.4.0 — 2026-08-10

- Extended persistent Undo/Redo history to approval/reopen and lock/unlock actions,
  including atomic history entries for bulk review operations.
- Undo and Redo menu items now name the exact operation that will be applied.
- Replace, Apply to matches, and Restore revision now participate in persistent
  Undo/Redo as atomic operations.
- AI Review results, reviewer candidates, and generated QA issues can now be undone
  and redone, including the completed part of a cancelled multi-batch review.
- Dismissing one or many AI review findings is now reversible through the same
  persistent Undo/Redo history.
- Undo/Redo now verifies QA issue snapshots as well as entry fields, preventing an
  older operation from overwriting validation results produced later.
- The History dock now shows recent project-wide operations with timestamps, applied
  or undone state, and the number of affected entries.
- Project creation and settings can generate an editable structured profile from the
  project name using the configured local Ollama model.
- Project-profile generation runs in a background worker with visible busy state, so
  slow local model responses no longer freeze the project dialog.
- When explicitly enabled in Privacy settings and selected in the project dialog,
  profile generation can enrich the local-model prompt with bounded Wikipedia search
  snippets; source localization strings are never sent.
- The File menu now exposes one format-agnostic Import files command and project-level
  Export selected / Export all commands instead of separate format-specific actions.
- The Project file tree now supports instant filtering by file name or relative path;
  selecting a filtered folder affects only its visible matching files.
- Project-tab keyboard navigation now routes Ctrl+F to file search, Ctrl+A to all
  visible files, and Escape to clearing the active filter or selection.
- The Project tab displays visible/total and selected file counts, making the scope of
  batch export, refresh, and removal explicit before running an action.
- Unified import preview now detects case-insensitive project-path conflicts against
  files already in the project and blocks the import before mapping dialogs are shown.
- Project paths can now be edited directly in the unified import preview, with live
  uniqueness and safety validation so conflicts can be fixed without selecting files again.
- Unified import can prepend a safe destination folder to every selected file in one
  action, making large batches easier to organize inside the project tree.

### Added

- Project-first workflow: empty projects can be created with a descriptive profile
  before localization files are imported.
- A single multi-select command adds JSON, CSV/TSV, PO, and XML files to the open
  project while preserving per-format mapping steps.
- Project Explorer now supports Windows-style multi-selection, filters the translation
  table by selected files, exports only the selected files, and opens project settings.
- Added central Translations and Project workspaces. The Project workspace shows file
  details and aggregate selection statistics, supports double-click navigation, and
  exposes common file operations through a context menu.
- Added a dedicated categorized application Settings dialog for appearance, editor,
  autosave, import/export confirmation, default project languages, and privacy choices.
- Project profile metadata is now assembled into a bounded, previewable AI context and
  supplied to both translation and reviewer prompts.
- Failed project opens can recover from the automatic `.lfproj.bak` copy without
  overwriting either the damaged original or its backup.
- Batch translation undo now supports persistent Redo with `Ctrl+Shift+Z`, including
  translation candidates, workflow status, and validation issues.
- Unified import now accepts drag-and-drop files and folders, recursively discovers
  supported formats, and previews the complete file set before format mapping/import.
- Folder imports preserve relative paths, allowing same-named localization files in
  different directories and restoring the directory tree during batch export.
- The Project workspace now renders a real expandable directory tree with format and
  progress columns; selecting a folder targets every localization file below it.
- Selected files or directory branches can be removed transactionally from a project;
  source files remain untouched while associated entries, QA, and history are cleaned.
- Newly imported documents retain their original source location for future refresh
  workflows, and the Project tree can open that location in the system file manager.
- Selected documents can be refreshed from source with a new/changed/removed preview;
  stable entries keep translations while changed source text is reopened for review.
- Manual translation edits now participate in the persistent Ctrl+Z/Ctrl+Shift+Z
  operation history, restoring both workflow status and validation state.

### Changed

- The File menu now centers on New Project, Open Project, and Add Files instead of
  separate format-specific project creation commands.

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
