
This repository holds a small package for post-processing coupled UM/NEMO runs to produce "cmore-lite" output.

Install the supported conda environment and the package from a clone of this repository:

```console
mamba env create -f environment.yaml
mamba activate ppfix
python -m pip install -e .
```

(`conda` can be used in place of `mamba`.)

Atmospheric processing repairs hybrid-height orography using the read-only
`assets/orographies_n1280.nc` file. Keep this asset in the clone when using the
editable installation above. Existing orography is squeezed to remove singleton
axes; otherwise, the matching latitude/longitude grid is inserted. Processing
raises an error if no grid matches. Other resolutions can supply a different
read-only file with `process_atmos(..., orography_file='/path/to/orographies.nc')`.
The helper is also available as
`ppfix.fixorography.fix_orography(field, orography_file=...)` and modifies the
in-memory field, not the source file.

Copy and edit `experiment_configs/n1280o12.conf` for the experiment being processed. Then copy (and rename) `examples/test_postproc.py` to your own project and edit it for directory-based runs.

The example shows separate `atmos`, `nemo`, and `sice` directories, but these can be the same. Note that there is an option to replace processed files or only process those which have not yet been procesed.

For large cycle directories on JASMIN, copy `examples/process_single_file.py` and
`examples/slurm_process_single_file_array.sh` into your working area and run one input file per Slurm array task.
Use `examples/generate_manifest.py` to build a text manifest of absolute input paths, then let each array task pick its own line from that manifest. If you pass a prefix such as `blah/1950`, the manifest generator will expand it to matching directories like `blah/195001/` and `blah/195002/` before collecting files.
For convenience, `examples/submit_process_single_file_array.sh` will build the manifest and submit the Slurm array in one step.
If some array tasks fail, `examples/find_failed_array_tasks.py` will scan the Slurm `.err` files, write a CSV summary of failed jobs, and create a manifest containing just the failed input files.

Atmospheric output safety
-------------------------

Atmospheric processing refuses to overwrite existing output files. Use a fresh
output directory for reruns. Before writing any fields from an input, all output
names are checked for collisions and existing targets. Colliding fields gain a
STASH-code suffix (or a NetCDF variable-name suffix when no STASH code exists).
Fields without a start date also gain their input filename as a suffix to avoid
collisions between array tasks. Ambiguous names raise an error instead of
silently dropping or replacing a field. Non-colliding dated filenames retain
their existing format.

Concatenation with provenance ancillaries
----------------------------------------

Use the public helper to concatenate already-read fields and preserve differing
scalar properties as field ancillaries:

```python
import cf
from ppfix import concatenate_with_ancillaries

# Supply files for one atomic dataset, ordered by time.
fields = []
for path in paths:
    result = cf.read(str(path), aggregate=False)
    if len(result) != 1:
        raise ValueError(f'Expected one field in {path}')
    fields.append(result[0])

combined = concatenate_with_ancillaries(fields, axis='T')
```

Common properties remain field attributes. Each non-common scalar property
becomes an ancillary along the concatenation axis, with the source value
repeated for every time step covered by that source. The helper does not modify
its input fields or read or write files. It relies on `cf.Field.concatenate`
for field compatibility; callers must supply correctly ordered inputs.

Empty input, non-common properties missing from an input, and non-scalar
non-common properties raise `ValueError`. Missing-value and vector-property
representations are not yet supported. CFA writing and incremental updates are
not part of this helper.
