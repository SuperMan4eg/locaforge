[English](architecture.md) | [Русский](architecture.ru.md)

# LocaForge architecture

## Purpose

LocaForge imports JSON, CSV/TSV, Gettext PO, and XML into a portable `.lfproj` project,
supports editing, validation, local-model translation and review, then reconstructs the
original format on export. User source files are never changed in place.

## Dependency rule

Dependencies point inward:

```text
Presentation ─┐
Infrastructure├──> Application ───> Domain
App/bootstrap ─┘
```

- `domain` contains entities, value objects, and business rules.
- `application` contains use cases, DTOs, `ProjectWorkspace`, and external ports.
- `infrastructure` implements file formats, SQLite persistence, `.lfproj`, Ollama, and metadata lookup.
- `presentation` contains PySide6 widgets, models, workers, and UI controllers.
- `app` is the composition root and application entry point.

`domain` and `application` do not import PySide6, `sqlite3`, HTTP clients, or concrete parsers.

## Package structure

```text
src/locaforge/
  app/                    # composition root, logging, startup
  domain/                 # projects, entries, profiles, settings, history
  application/
    ports/                # persistence, formats, LLM, metadata, glossary, TM
    use_cases/            # import/export, edit, translate, validate, review
    dto/                  # boundary data
    services/             # cross-use-case application services
  infrastructure/
    formats/              # JSON, CSV/TSV, PO, XML
    persistence/          # SQLite and .lfproj container
    llm/                  # Ollama client
    metadata/             # optional online project metadata
  presentation/           # Qt UI, controllers, workers, localization
  resources/locales/      # bundled interface language packages
```

## Main flows

Importers parse a source file into format-neutral entries plus round-trip metadata. Use
cases operate only on domain objects and ports. The SQLite repository persists the project;
the `.lfproj` container packages that database for transport. Exporters combine current
translations with the stored metadata and write a new destination file transactionally.

Translation and review resolve the effective [model settings](development.md#model-settings-inheritance),
build bounded project context, call the LLM port, validate the result, and record a reversible
operation. Presentation controllers coordinate these flows without owning business rules.

## Persistence and compatibility

A project can contain multiple documents and formats. Stable entry and document identifiers
support filtering, refresh, history, and batch operations. Schema migrations happen when a
container is opened; old containers remain readable. Containers verify their ZIP data and SQLite
database integrity before use. Manual saves atomically replace the target and retain three backup
generations: `.lfproj.bak` is the newest, followed by `.bak.1` and `.bak.2`. Failed opens may
recover from the newest backup without overwriting either original file.

## Extension points

Add a file format by implementing the importer/exporter ports and registering them in the
composition root. Add an LLM backend behind the LLM port. Add UI languages as described in
[Custom localization](localization.md); language packages do not alter domain behavior.

## Current boundaries

LocaForge is a single-user desktop application. It does not provide collaborative editing,
a hosted model backend, or direct mutation of source files.
