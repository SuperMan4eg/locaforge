[English](performance-stage7.md) | [Русский](performance-stage7.ru.md)

# Runtime and compiler experiment

The stage-7 experiment was run on 11 August 2026 with CPython 3.14.6, PySide6
6.11.1, MSVC 14.51, Cython 3.2.9, and Nuitka 4.1.3. The working tree already
contained the stage 0–6 performance changes. Every comparison used the same
code and fixture configuration.

## Decision

Keep the production runtime and Windows packaging unchanged:

- leave the experimental CPython JIT disabled;
- do not add a Cython extension for consistency validation;
- continue using PyInstaller for release bundles;
- retain the experiment scripts and measurements so the decision can be
  revisited after Nuitka has non-experimental Python 3.14 support or a new
  measured CPU hotspot appears.

None of the tested alternatives met the project's 15% user-scenario improvement
threshold without adding material build or compatibility risk.

## CPython JIT

The full benchmark was run with seven measured iterations and three warmups for
10,000- and 50,000-entry projects. `PYTHON_JIT=1` was verified at runtime.

The geometric mean changed by approximately `-0.33%` in elapsed time. Individual
results moved in both directions, including slower project statistics and entry
lookup measurements. This is indistinguishable from workload and system noise,
so the JIT remains disabled.

Raw reports:

- `benchmarks/stage7-cpython314-jit-off.json`
- `benchmarks/stage7-cpython314-jit-on.json`

## Cython

The real `ConsistencyValidator` service was compiled as an isolated extension
and measured over 50,000 entries for 50 iterations after ten warmups.

| Runtime | Median |
| --- | ---: |
| CPython | 15.387 ms |
| Cython | 15.348 ms |

The `1.0025x` result is effectively no improvement. The first build also showed
a compatibility hazard: Cython's annotation typing treated a `dict[...]`
annotation as an exact type and rejected the service's `defaultdict`. Safe
Python semantics required `annotation_typing=False`, which also leaves little
optimization opportunity in this object-heavy code.

Raw report: `benchmarks/stage7-cython-consistency.json`.

## Nuitka

Both packaging candidates were built from the same tree and passed `--self-test`
and `--smoke-test`. Startup uses 20 measured offscreen smoke runs after three
warmups.

| Packaging | Startup median | p95 | Distribution size |
| --- | ---: | ---: | ---: |
| PyInstaller 6.21.0 | 347.469 ms | 352.058 ms | 128,884,164 bytes |
| Nuitka 4.1.3 | 315.066 ms | 318.171 ms | 92,619,856 bytes |

Nuitka starts `9.3%` faster and is `28.1%` smaller. The compiled benchmark's
geometric mean is only about `2.2%` faster than CPython. Text filtering improves
by roughly 25%, while project statistics and entry lookup regress by more than
20% in some fixture sizes. Nuitka also warns that Python 3.14 support is still
experimental in version 4.1.3.

The startup improvement is useful but below the 15% acceptance threshold, and
the mixed internal results do not justify replacing the stable release pipeline.

Raw reports:

- `benchmarks/stage7-packaging.json`
- `benchmarks/stage7-nuitka-runtime.json`

## Reproduction

Install the optional experiment tools and run the checked-in scripts:

```powershell
python -m pip install -e ".[experiment]"
$env:PYTHONPATH = "src"
$env:QT_QPA_PLATFORM = "offscreen"

.\scripts\build_nuitka_experiment.ps1
.\scripts\build_nuitka_benchmark_experiment.ps1

python scripts\build_cython_experiment.py build_ext `
  --build-lib build\stage7-cython\lib `
  --build-temp build\stage7-cython\temp
python scripts\benchmark_cython_experiment.py `
  --extension-dir build\stage7-cython\lib
```

Generated binaries and compiler intermediates remain under the ignored `build/`
directory.
