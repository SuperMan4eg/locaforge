# LocaForge performance baseline

Generated: `2026-08-11T14:39:21.979342+00:00`

| Scenario | Size | Median, ms | p95, ms | Min, ms | Max, ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cold_ui_startup` | 0 | 463.593 | 468.192 | 457.197 | 468.192 |
| `project_entry_lookup_1000` | 10000 | 0.158 | 0.293 | 0.139 | 0.293 |
| `project_statistics` | 10000 | 1.420 | 1.695 | 1.317 | 1.695 |
| `table_text_filter` | 10000 | 12.292 | 12.445 | 12.234 | 12.445 |
| `table_document_filter` | 10000 | 7.488 | 7.683 | 7.454 | 7.683 |
| `table_update_last_entry` | 10000 | 0.007 | 0.008 | 0.007 | 0.008 |
| `project_explorer_refresh` | 10000 | 6.308 | 6.588 | 6.096 | 6.588 |
| `open_lfproj` | 10000 | 59.196 | 70.293 | 57.908 | 70.293 |
| `edit_translation` | 10000 | 53.142 | 65.634 | 52.664 | 65.634 |
| `undo_redo_cycle` | 10000 | 7.303 | 7.827 | 7.085 | 7.827 |
| `validate_project` | 10000 | 94.465 | 104.947 | 93.670 | 104.947 |
| `repository_full_save` | 10000 | 71.603 | 84.777 | 70.440 | 84.777 |
| `manual_save_lfproj` | 10000 | 58.270 | 71.173 | 56.937 | 71.173 |
| `autosave_lfproj` | 10000 | 22.848 | 28.137 | 21.936 | 28.137 |
| `project_entry_lookup_1000` | 50000 | 0.159 | 0.166 | 0.154 | 0.166 |
| `project_statistics` | 50000 | 9.729 | 9.855 | 9.618 | 9.855 |
| `table_text_filter` | 50000 | 61.918 | 65.687 | 61.389 | 65.687 |
| `table_document_filter` | 50000 | 37.019 | 37.283 | 36.738 | 37.283 |
| `table_update_last_entry` | 50000 | 0.007 | 0.008 | 0.007 | 0.008 |
| `project_explorer_refresh` | 50000 | 18.055 | 18.415 | 17.484 | 18.415 |
| `open_lfproj` | 50000 | 310.177 | 318.358 | 281.204 | 318.358 |
| `edit_translation` | 50000 | 256.430 | 270.842 | 236.818 | 270.842 |
| `undo_redo_cycle` | 50000 | 7.937 | 8.518 | 7.442 | 8.518 |
| `validate_project` | 50000 | 522.121 | 524.608 | 519.157 | 524.608 |
| `repository_full_save` | 50000 | 611.933 | 620.062 | 602.421 | 620.062 |
| `manual_save_lfproj` | 50000 | 304.224 | 314.770 | 276.272 | 314.770 |
| `autosave_lfproj` | 50000 | 79.171 | 81.346 | 78.244 | 81.346 |
| `translation_memory_similar` | 10000 | 2.205 | 2.294 | 2.163 | 2.294 |
| `glossary_batch_match` | 500 | 38.331 | 38.814 | 37.635 | 38.814 |

## Environment

- python: `3.14.6`
- python_implementation: `CPython`
- python_jit_available: `True`
- python_jit_enabled: `True`
- python_gil_enabled: `True`
- pyside: `6.11.1`
- platform: `Windows-11-10.0.26200-SP0`
- processor: `Intel64 Family 6 Model 198 Stepping 2, GenuineIntel`
- sqlite: `3.50.4`
