# LocaForge performance baseline

Generated: `2026-08-11T14:38:39.529961+00:00`

| Scenario | Size | Median, ms | p95, ms | Min, ms | Max, ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cold_ui_startup` | 0 | 471.267 | 475.894 | 466.563 | 475.894 |
| `project_entry_lookup_1000` | 10000 | 0.139 | 0.141 | 0.137 | 0.141 |
| `project_statistics` | 10000 | 1.357 | 1.513 | 1.324 | 1.513 |
| `table_text_filter` | 10000 | 12.429 | 12.944 | 12.383 | 12.944 |
| `table_document_filter` | 10000 | 7.099 | 7.680 | 6.960 | 7.680 |
| `table_update_last_entry` | 10000 | 0.007 | 0.008 | 0.007 | 0.008 |
| `project_explorer_refresh` | 10000 | 6.452 | 7.311 | 6.190 | 7.311 |
| `open_lfproj` | 10000 | 60.623 | 89.306 | 58.948 | 89.306 |
| `edit_translation` | 10000 | 54.041 | 67.311 | 52.897 | 67.311 |
| `undo_redo_cycle` | 10000 | 7.941 | 9.591 | 7.685 | 9.591 |
| `validate_project` | 10000 | 95.518 | 117.663 | 95.158 | 117.663 |
| `repository_full_save` | 10000 | 73.006 | 77.304 | 71.829 | 77.304 |
| `manual_save_lfproj` | 10000 | 58.577 | 70.883 | 57.596 | 70.883 |
| `autosave_lfproj` | 10000 | 23.578 | 25.822 | 22.125 | 25.822 |
| `project_entry_lookup_1000` | 50000 | 0.158 | 0.199 | 0.156 | 0.199 |
| `project_statistics` | 50000 | 7.525 | 7.812 | 7.484 | 7.812 |
| `table_text_filter` | 50000 | 62.480 | 63.208 | 61.241 | 63.208 |
| `table_document_filter` | 50000 | 37.307 | 41.476 | 34.601 | 41.476 |
| `table_update_last_entry` | 50000 | 0.007 | 0.007 | 0.006 | 0.007 |
| `project_explorer_refresh` | 50000 | 22.923 | 24.291 | 19.582 | 24.291 |
| `open_lfproj` | 50000 | 314.999 | 340.360 | 285.111 | 340.360 |
| `edit_translation` | 50000 | 264.377 | 271.933 | 236.451 | 271.933 |
| `undo_redo_cycle` | 50000 | 7.446 | 7.934 | 6.926 | 7.934 |
| `validate_project` | 50000 | 522.529 | 527.047 | 519.759 | 527.047 |
| `repository_full_save` | 50000 | 611.005 | 646.850 | 601.431 | 646.850 |
| `manual_save_lfproj` | 50000 | 303.032 | 312.061 | 277.271 | 312.061 |
| `autosave_lfproj` | 50000 | 80.739 | 87.707 | 75.400 | 87.707 |
| `translation_memory_similar` | 10000 | 2.252 | 2.303 | 2.210 | 2.303 |
| `glossary_batch_match` | 500 | 38.886 | 39.211 | 38.711 | 39.211 |

## Environment

- python: `3.14.6`
- python_implementation: `CPython`
- python_jit_available: `True`
- python_jit_enabled: `False`
- python_gil_enabled: `True`
- pyside: `6.11.1`
- platform: `Windows-11-10.0.26200-SP0`
- processor: `Intel64 Family 6 Model 198 Stepping 2, GenuineIntel`
- sqlite: `3.50.4`
