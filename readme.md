
This repository holds a small package for post-processing coupled UM/NEMO runs to produce "cmore-lite" output.

Install the supported conda environment and the package from a clone of this repository:

```console
mamba env create -f environment.yaml
mamba activate ppfix
python -m pip install .
```

(`conda` can be used in place of `mamba`.)

Copy and edit `experiment_configs/n1280o12.conf` for the experiment being processed. Then copy
`examples/test_postproc.py` to your own project, or run it directly:

```console
python examples/test_postproc.py INPUT_DIRECTORY OUTPUT_DIRECTORY METADATA_FILE
```

The output directory receives separate `atmos`, `nemo`, and `sice` directories. Existing ocean and sea-ice files are skipped by default; pass `--replace` to overwrite them.
