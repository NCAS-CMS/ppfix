# CFA aggregation versus concatenation experiment

## Purpose and scope

Compare multi-file aggregation with individual reads followed by direct time
concatenation for one atomic dataset. Quality takes priority over speed: the
experiment does not establish that either path is ready for production CFA output.

Run on 2026-11-10 using cf-python 3.21.0 in the existing `ppfix` conda environment.
The installed direct-concatenation API is `cf.Field.concatenate`, not
`cf.concatenate`.

## Inputs

- Simulation: `~/hrcm/simulations/u-dz876`.
- Resolved location: `/gws/ssde/j25a/hrcm/simulations/u-dz876`.
- Domain: `atmos`.
- Atomic dataset: monthly zonal-mean air temperature, pressure coordinate `p36`.
- Filename pattern: `*__monthlyzm__*__mean__air_temperature__p36__*.nc`.
- 120 files, January 1950 through December 1959, totalling 26,655,085 bytes.
- Result shape: `(120, 36, 1921, 1)`; dtype: `float32`.

Inputs were resolved to absolute physical paths and sorted by filename. That
ordering corresponds to time for this dataset; a general workflow must validate
actual time coordinates rather than assume filename order is sufficient.

## Method

Compare these paths using the same fixed input list:

1. `cf.read(paths)`, with its default internal aggregation.
2. `cf.read(path, aggregate=False)` for each file, followed by
   `cf.Field.concatenate(fields, axis="T")`.

Warm both paths once, then run three measured trials in alternating order:
aggregation/concatenation, concatenation/aggregation, aggregation/concatenation.
Use Dask's synchronous scheduler to limit concurrency in the shared environment.

Timings include reads and lazy field construction, but exclude equality checks,
payload materialisation during those checks, and CFA writing. No attempt was made
to flush shared filesystem caches. These are warmed-cache measurements on this
storage and dataset, not a general performance guarantee.

## Results

| Trial | Aggregation (s) | Individual reads (s) | Concatenation (s) | Reads + concatenation (s) |
|---|---:|---:|---:|---:|
| 1 | 16.529 | 5.747 | 0.332 | 6.079 |
| 2 | 16.434 | 5.656 | 0.184 | 5.840 |
| 3 | 16.115 | 5.826 | 0.338 | 6.164 |
| Median | 16.434 | | | 6.079 |

Individual reads plus concatenation were about 2.70 times faster by median elapsed
time. Warmup times were 18.198 s for aggregation and 6.422 s for concatenation.

An initial 12-file check failed strict whole-field equality because the two
methods handled three properties differently. All three 120-file trials then
passed `Field.equals` with zero relative and absolute tolerances, excluding only
those explicitly identified properties:

- `original_output`
- `tracking_id`
- `start_date`

Thus data, missing-data masks, coordinates and bounds, dtype, and remaining CF
metadata matched exactly according to `Field.equals`. NetCDF variable and
dimension names are not checked by that method. This was an in-memory comparison,
not a CFA write/read round trip.

Aggregation joined the differing property values with ` :AGGREGATED: `.
Direct concatenation retained the first input file's values. Neither behaviour
meets the revised metadata requirement.

## Revised quality requirement

Properties common to all inputs may remain properties of the output field.
Anything not common to the inputs must instead be represented as ancillary
variables in the CFA output, preserving its association with the relevant source
and time coverage. Do not join values into strings or silently retain only the
first input's value.

This applies to all non-common metadata, not just the three properties observed
here. Missing properties must remain distinguishable from present values.
The exact ancillary representation, including string values and alignment when
one source covers multiple time steps, still needs to be designed and verified
with cf-python and the applicable CF conventions.

Before production use, verify that a CFA write/read round trip preserves both the
scientific content and the ancillary metadata. Incremental updates must preserve
old provenance and correctly associate new provenance with new time coverage.
The benchmark's ignored properties are a diagnostic exception, not an acceptable
production equality criterion.

## Reproduction

Run from the existing cf-python environment with bytecode writing disabled:

```console
conda activate ppfix
python -B - <<'PY'
from pathlib import Path
from statistics import median
from time import perf_counter
import gc

import cf
import dask

root = Path("~/hrcm/simulations/u-dz876/atmos").expanduser().resolve()
paths = sorted(root.glob("*__monthlyzm__*__mean__air_temperature__p36__*.nc"))
if len(paths) < 2:
    raise RuntimeError("Need at least two input files")
snapshot = [(p.stat().st_size, p.stat().st_mtime_ns) for p in paths]
provenance = ("original_output", "tracking_id", "start_date")


def aggregate():
    start = perf_counter()
    result = cf.read([str(p) for p in paths])
    elapsed = perf_counter() - start
    if len(result) != 1:
        raise RuntimeError(f"Expected one aggregated field, got {len(result)}")
    return result[0], elapsed, None


def concatenate():
    start = perf_counter()
    fields = []
    for path in paths:
        result = cf.read(str(path), aggregate=False)
        if len(result) != 1:
            raise RuntimeError(f"{path}: expected one field, got {len(result)}")
        fields.append(result[0])
    read_seconds = perf_counter() - start
    start_join = perf_counter()
    field = cf.Field.concatenate(fields, axis="T")
    join_seconds = perf_counter() - start_join
    return field, read_seconds + join_seconds, (read_seconds, join_seconds)


print("cf-python:", cf.__version__)
print("Files:", len(paths), "bytes:", sum(size for size, _ in snapshot))
print("First:", paths[0], "Last:", paths[-1])
with dask.config.set(scheduler="synchronous"):
    for operation in (aggregate, concatenate):
        field, elapsed, _ = operation()
        print("Warmup:", operation.__name__, elapsed)
        del field
        gc.collect()

    samples = {"aggregate": [], "concatenate": []}
    orders = ((aggregate, concatenate), (concatenate, aggregate),
              (aggregate, concatenate))
    for trial, order in enumerate(orders, 1):
        outputs = {}
        for operation in order:
            field, elapsed, components = operation()
            samples[operation.__name__].append(elapsed)
            outputs[operation.__name__] = field
            print(trial, operation.__name__, elapsed, "read/join:", components)
        a, c = outputs["aggregate"], outputs["concatenate"]
        ap, cp = a.properties(), c.properties()
        differences = [key for key in sorted(ap.keys() | cp.keys())
                       if key not in ap or key not in cp
                       or str(ap[key]) != str(cp[key])]
        print("Differing field properties:", differences)
        if set(differences) != set(provenance):
            raise RuntimeError("Unexpected metadata differences")
        if not a.equals(c, ignore_properties=provenance, rtol=0, atol=0,
                        verbose=2):
            raise RuntimeError("Scientific content or other metadata differs")
        print("Exact equality excluding reported provenance: True")
        print("Shape:", a.shape, "dtype:", a.dtype)
        del outputs, a, c, field
        gc.collect()

    for name, values in samples.items():
        print(name, "seconds:", values, "median:", median(values))
    print("Speedup:", median(samples["aggregate"]) / median(samples["concatenate"]))

if snapshot != [(p.stat().st_size, p.stat().st_mtime_ns) for p in paths]:
    raise RuntimeError("Source size or modification time changed during the run")
print("No output files written; source sizes and modification times unchanged")
PY
```

The property-difference listing uses string representations as a diagnostic; the
subsequent `Field.equals` call performs the scientific comparison. A production
metadata classifier must compare property types and values explicitly.

No source files or CFA files were created, overwritten, or modified by the
experiment. This note records an experiment, not an implementation of CFA
creation or updates.

## Regression tests

`tests/test_cfa_aggregation.py` contains:

- An in-memory unit test using `cf.example_field(2)`, split into three unequal
  time segments. Both aggregation and direct concatenation must reproduce the
  original 24-step field exactly, including its time bounds.
- A real-data regression test using 24 byte-for-byte copies of the January 1950
  through December 1951 inputs under
  `tests/data/cfa/monthlyzm_air_temperature_p36/`. Tests read these local copies,
  not the live simulation folder. Do not overwrite or modify these data files.

The real-data test checks the output shape, float32 dtype, chronological time
ordering, and exact scientific equivalence. It explicitly identifies the three
provenance-property differences before excluding them from `Field.equals`.
This documents the current metadata limitation; it does not test or implement
the required ancillary-variable preservation or a CFA write/read round trip.

Run the tests in the existing `ppfix` environment:

```console
PYTHONDONTWRITEBYTECODE=1 python -B -m pytest -p no:cacheprovider -s tests/test_cfa_aggregation.py
```

The real-data test prints read/construction timings and records them as pytest
properties. It deliberately has no speed threshold: a single un-warmed test run
is a correctness regression check, not a controlled performance benchmark.

### Additional full-provenance test

`test_real_file_concatenation_with_ancillaries_fully_matches_aggregation` is an
additional test; the two original tests remain unchanged.

It reads the same 24 local files once, collects their properties, and discovers
all non-common properties rather than hard-coding the three observed names.
For the independent reference, it uses
`cf.aggregate(fields, axes='T', field_ancillaries=non_common)`, not the default
aggregation behaviour that joins attribute strings.

The concatenation path creates its ancillary constructs separately, after
concatenation, from the collected source properties. Each scalar property value
is repeated for the number of time steps in its source field, and the original
non-common field attribute is removed. Common attributes remain untouched.
The test explicitly fails if it encounters missing or non-scalar non-common
properties: their representation is not resolved by this scalar-property
experiment.

For both outputs, the test checks that each discovered property is an ancillary,
not a field attribute, that its axis is time, and that its values match each
source's property over the relevant time steps. Finally, it asserts full
`Field.equals(..., rtol=0, atol=0)` with no ignored properties. Any mismatch fails
the test.

This adds an in-memory check of provenance preservation; CFA writing, round-trip
validation, and incremental updates remain future work.
