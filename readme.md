
This repository holds a small package for post-processing coupled UM/NEMO runs to produce "cmore-lite" output.

Install the supported conda environment and the package from a clone of this repository:

```console
mamba env create -f environment.yaml
mamba activate ppfix
python -m pip install .
```

(`conda` can be used in place of `mamba`.)

Copy and edit `experiment_configs/n1280o12.conf` for the experiment being processed. Then copy (and rename) `examples/test_postproc.py` to your own project and edit it for directory-based runs.

The example shows separate `atmos`, `nemo`, and `sice` directories, but these can be the same. Note that there is an option to replace processed files or only process those which have not yet been procesed.

For large cycle directories on JASMIN, copy `examples/process_single_file.py` and
`examples/slurm_process_single_file_array.sh` into your working area and run one input file per Slurm array task.
Use `examples/generate_manifest.py` to build a text manifest of absolute input paths, then let each array task pick its own line from that manifest. If you pass a prefix such as `blah/1950`, the manifest generator will expand it to matching directories like `blah/195001/` and `blah/195002/` before collecting files.
For convenience, `examples/submit_process_single_file_array.sh` will build the manifest and submit the Slurm array in one step.

