[English](mvp-contracts.md) | [Русский](mvp-contracts.ru.md)

# MVP contracts

## Domain entities

### `TranslationEntry`

An entry has a stable ID, source path/text, optional translation, workflow status, lock state,
candidate translations, and validation issues. Editing a translation reopens the entry when
required and records a reversible operation. Locked entries cannot be changed by batch AI flows.

### `Project`

A project has an ID, name, language pair, documents, entries, profile, model-settings snapshot,
override flag, and dirty state. It owns consistency rules but knows nothing about files, SQLite,
Qt, or HTTP. A project may contain multiple documents with safe unique relative paths.

## Application ports

### `ProjectRepository`

Loads and saves projects and their entries, validation issues, revisions, history operations,
glossary, and translation memory. Multi-entity mutations required by one user action are atomic.

### `ProjectContainer`

Packs and opens portable `.lfproj` files. Writes use a temporary destination and replacement;
opening supports schema migration and recovery diagnostics. The container never overwrites an
unrelated source localization file.

### Importers and exporters

Importers convert supported source formats into normalized documents and round-trip metadata.
Exporters reconstruct the same semantic format at a caller-selected destination. Format-specific
mapping is explicit and reusable where supported. See the [JSON contract](json-round-trip.md).

### `LLMClient`

Lists and pulls local models and performs translation, review, and project-profile generation.
Requests receive explicit settings and bounded context. Infrastructure errors are translated into
application-facing failures; cancellation preserves the completed part as one reversible operation.

### Translation and review services

Services protect placeholders, apply glossary/context, validate structured model output, and
return DTOs rather than mutating UI state. The effective model profile follows the inheritance
rules in the [developer guide](../docs/development.md#model-settings-inheritance).

## Behavioral guarantees

- original input files remain unchanged;
- export is transactional and preserves format semantics;
- project paths are relative, normalized, unique case-insensitively, and cannot escape the project;
- persisted operations support Undo/Redo with conflict checks against newer state;
- failures contain actionable context and do not leave partially committed project state;
- presentation code invokes use cases and does not implement domain rules.

## Error categories

Expected errors include invalid input/mapping, project not found or corrupt, unsafe/conflicting
path, unavailable model/backend, invalid model response, validation failure, cancellation, and
destination I/O failure. UI adapters may localize these errors but must not discard their cause.
