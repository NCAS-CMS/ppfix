
This repository holds a small package for post-processing coupled UM/NEMO runs to produce "cmore-lite" output.

Install it into a conda environment using:
 
`conda env create -f environment.yaml`

You want to copy the configuration file `n1280o12.conf` from the `experiment_configs` folder into your own folder, 
and edit it so the information is as you want it to be.

You can then copy the `examples/test_postproc.py` file, and use it for your own script, directing the output
to the folders of your choice.
