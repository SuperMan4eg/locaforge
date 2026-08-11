# LocaForge performance baseline

Generated: `2026-08-11T14:27:37.838756+00:00`

| Scenario | Size | Median, ms | p95, ms | Min, ms | Max, ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| `project_entry_lookup_1000` | 1 | 0.001 | 0.004 | 0.001 | 0.004 |
| `project_statistics` | 1 | 0.003 | 0.006 | 0.002 | 0.006 |
| `table_text_filter` | 1 | 0.006 | 0.016 | 0.004 | 0.016 |
| `table_document_filter` | 1 | 0.003 | 0.004 | 0.003 | 0.004 |
| `table_update_last_entry` | 1 | 0.011 | 0.014 | 0.009 | 0.014 |
| `project_explorer_refresh` | 1 | 0.088 | 0.128 | 0.073 | 0.128 |
| `open_lfproj` | 1 | 3.135 | 3.241 | 3.053 | 3.241 |
| `edit_translation` | 1 | 7.806 | 8.014 | 7.563 | 8.014 |
| `undo_redo_cycle` | 1 | 7.344 | 7.520 | 6.914 | 7.520 |
| `validate_project` | 1 | 0.891 | 1.070 | 0.862 | 1.070 |
| `repository_full_save` | 1 | 3.474 | 3.833 | 3.443 | 3.833 |
| `manual_save_lfproj` | 1 | 3.317 | 3.508 | 3.111 | 3.508 |
| `autosave_lfproj` | 1 | 5.924 | 6.805 | 5.424 | 6.805 |
| `translation_memory_similar` | 1 | 0.247 | 0.279 | 0.244 | 0.279 |
| `glossary_batch_match` | 1 | 0.002 | 0.004 | 0.001 | 0.004 |
| `ollama_generate_batch` | 5 | 2437.028 | 4027.513 | 2425.669 | 4027.513 |
| `ollama_generate_batch` | 10 | 5180.624 | 5817.918 | 4361.919 | 5817.918 |
| `ollama_generate_batch` | 20 | 11314.832 | 11569.863 | 11278.555 | 11569.863 |
| `ollama_generate_batch` | 40 | 22477.306 | 22790.975 | 17181.599 | 22790.975 |

## Environment

- python: `3.14.6`
- python_implementation: `CPython`
- pyside: `6.11.1`
- platform: `Windows-11-10.0.26200-SP0`
- processor: `Intel64 Family 6 Model 198 Stepping 2, GenuineIntel`
- sqlite: `3.50.4`
