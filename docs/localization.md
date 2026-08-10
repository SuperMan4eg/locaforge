[English](localization.md) | [Русский](localization.ru.md)

# Creating a custom interface localization

LocaForge bundles English and Russian and loads additional JSON language packages from the
user localization directory. Open Settings → Language to locate that directory, reload
packages, and view validation diagnostics.

## Create a package

1. Start LocaForge once. It creates `template.json` in the user localization directory.
2. Copy the template to a descriptive file such as `de.json`; do not edit the template itself.
3. Set `metadata.locale` to a BCP 47-style code and `metadata.name` to the display name.
4. Translate values in `messages`. Keep every key and all `{named_parameters}` unchanged.
5. Save as UTF-8 JSON, reload language packages in Settings, and resolve all errors.
6. Select the new language. Regional requests such as `de-DE` fall back to an installed
   package with the same base language, then to English.

Minimal structure:

```json
{
  "metadata": {
    "locale": "de",
    "name": "Deutsch",
    "fallback": "en",
    "format_version": 1
  },
  "messages": {
    "app.title": "LocaForge",
    "example.count": "{count} Einträge"
  }
}
```

Use the complete generated template: the abbreviated example is not a complete package.

## Validation rules

- the root contains `metadata` and `messages` objects;
- `locale`, `name`, and `fallback` are non-empty strings;
- `fallback` is `en` and `format_version` is `1`;
- message keys and values are non-empty strings;
- custom packages cannot replace built-in English or introduce unknown keys;
- missing English keys are warnings and use the English text at runtime;
- named parameters must exactly match the English message.

Invalid JSON or schema errors prevent the package from loading. A bad individual lookup never
crashes the UI: LocaForge records a diagnostic and uses the safest available message.

## Updating a package

When LocaForge adds strings, compare your package with the newly generated template or bundled
`src/locaforge/resources/locales/en.json`. Add the new keys, preserve parameters, increment only
the package content—not `format_version`—and validate again.

To contribute a bundled language, include the JSON package, localization tests, and updates to
both [English](../README.md) and [Russian](../README.ru.md) documentation.
