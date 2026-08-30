
This repository holds a small package for post-processing coupled UM/NEMO runs to produce "cmore-lite" output.

Install the supported conda environment and the package from a clone of this repository:

```console
mamba env create -f environment.yaml
mamba activate ppfix
python -m pip install .
```

(`conda` can be used in place of `mamba`.)

Copy and edit `experiment_configs/n1280o12.conf` for the experiment being processed. Then copy (and rename) `examples/test_postproc.py` to your own project and edit it for your data layout.

The example shows separate `atmos`, `nemo`, and `sice` directories, but these can be the same. Note that there is an option to replace processed files or only process those which have not yet been procesed.

