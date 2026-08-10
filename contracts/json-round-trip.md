[English](json-round-trip.md) | [Русский](json-round-trip.ru.md)

# JSON round-trip contract

## Supported input

The root is a JSON object or array. Strings selected by the import mapping become translation
entries. Objects, arrays, numbers, booleans, nulls, unselected strings, key order, and Unicode
text are retained as round-trip metadata.

## Import

Each selected string receives a stable path and entry identifier. Object keys use dotted path
segments and array elements use numeric indexes. Import never mutates the source file. Invalid
JSON, unsupported roots, unsafe mappings, and duplicate project paths fail before persistence.

## Export

Export starts from the stored source document, replaces only selected string values with their
current translations, and writes a separate destination. Missing translations retain the source
text. The operation is transactional: validation or write failure must not leave a partial output.

The contract guarantees semantic JSON round-trip, not byte identity. Whitespace, indentation,
escaping, and final newline may be normalized; data types and unselected values must not change.

## Acceptance examples

For `{"menu":{"play":"Play"},"lives":3}`, selecting `menu.play` and translating it to
`Играть` exports `{"menu":{"play":"Играть"},"lives":3}`. The number remains a number.

For `["One", {"enabled": true}]`, selecting index `0` changes only that string. The object and
boolean remain intact. If the translation is empty or absent, `"One"` is retained.

## Errors

Importer and exporter errors include enough file and path context for the application layer to
report an actionable message. Format adapters raise domain/application-facing errors rather than
showing UI dialogs.
