# LocaForge performance baseline

Generated: `2026-08-11T14:49:26.797424+00:00`

| Scenario | Size | Median, ms | p95, ms | Min, ms | Max, ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| `project_entry_lookup_1000` | 10000 | 0.170 | 0.269 | 0.169 | 0.269 |
| `project_statistics` | 10000 | 1.686 | 1.786 | 1.671 | 1.786 |
| `table_text_filter` | 10000 | 9.333 | 9.380 | 9.294 | 9.380 |
| `table_document_filter` | 10000 | 6.437 | 6.581 | 6.420 | 6.581 |
| `table_update_last_entry` | 10000 | 0.006 | 0.007 | 0.006 | 0.007 |
| `project_explorer_refresh` | 10000 | 6.699 | 7.164 | 6.536 | 7.164 |
| `open_lfproj` | 10000 | 59.704 | 70.914 | 58.499 | 70.914 |
| `edit_translation` | 10000 | 53.360 | 65.702 | 52.229 | 65.702 |
| `undo_redo_cycle` | 10000 | 7.502 | 8.031 | 7.092 | 8.031 |
| `validate_project` | 10000 | 106.499 | 120.219 | 105.195 | 120.219 |
| `repository_full_save` | 10000 | 71.706 | 78.113 | 71.517 | 78.113 |
| `manual_save_lfproj` | 10000 | 60.560 | 74.157 | 59.505 | 74.157 |
| `autosave_lfproj` | 10000 | 24.082 | 27.183 | 22.810 | 27.183 |
| `project_entry_lookup_1000` | 50000 | 0.176 | 0.193 | 0.175 | 0.193 |
| `project_statistics` | 50000 | 9.299 | 9.435 | 9.065 | 9.435 |
| `table_text_filter` | 50000 | 47.160 | 47.533 | 46.874 | 47.533 |
| `table_document_filter` | 50000 | 32.664 | 32.910 | 32.534 | 32.910 |
| `table_update_last_entry` | 50000 | 0.006 | 0.007 | 0.006 | 0.007 |
| `project_explorer_refresh` | 50000 | 18.366 | 18.902 | 18.151 | 18.902 |
| `open_lfproj` | 50000 | 291.157 | 323.646 | 288.745 | 323.646 |
| `edit_translation` | 50000 | 250.309 | 279.310 | 244.390 | 279.310 |
| `undo_redo_cycle` | 50000 | 7.473 | 7.760 | 7.134 | 7.760 |
| `validate_project` | 50000 | 548.759 | 581.794 | 544.296 | 581.794 |
| `repository_full_save` | 50000 | 611.889 | 620.655 | 597.642 | 620.655 |
| `manual_save_lfproj` | 50000 | 283.128 | 319.403 | 280.231 | 319.403 |
| `autosave_lfproj` | 50000 | 80.744 | 85.489 | 79.404 | 85.489 |
| `translation_memory_similar` | 10000 | 2.234 | 2.299 | 2.208 | 2.299 |
| `glossary_batch_match` | 500 | 39.782 | 40.477 | 39.081 | 40.477 |

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
