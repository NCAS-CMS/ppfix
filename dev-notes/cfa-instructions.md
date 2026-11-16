#### Goal

Our next step will be to create CFA files, one per variable, for the contents of the simuation folder. 

A reminder that CFA files are netcdf files that conform to the cf-conventions that point to files elsewhere. They can be created and consumed by cf-python.

The simulation folder may vary, but for this first application, we can assume it is `~/hrcm/simulations/u-dz876` (clearly this should be configurable).

We want our CFA output files to appear in a configurable folder, in this instance it will be `~/hrcm/simulations/CFA/u-dz876`.  

When we are building the CFA files we want the full absolute path to the child files, not the relative path via my logical link.

We want to do this for all the data held in the simulation folder, not just the atmos data.

#### Context

This workflow has to assume that the number of files will be growing, so let's first describe the background workflow:

- model simulations are arriving on disk, and being converted using ppfix into files which will be present in the source folder folder in subfolders atmos,ocean,seaice.

- at any given time, we want to create CFA files for what we have, but we can expect to have to update them in the future (as new files appear).

- Our problem is that on first run, we can produce a CFA file for all variables for the data in the source folders, but at a future time, there could be new files as well as old files.

- We could ensure that every CFA file has an attribute that is the "CFA_creation_time" which is the time used to do a glob of files to be used as the input for the CFA ... and then then next time we run, we check for an existing CFA file, and glob only the files that came after that time, and then concatenate the existing CFA with the new files.

#### Methodology

We have two options for how to do this, in both cases we loop over atomic datasets (unique combinatinos of variable id, vertical coordinate, and temporal averaging), creating a CFA file for each atomic dataset. Then:

1. We can have a read loop over those files, so we then have a set of cf fields, which we then cf.concatenate (because we know they will concatenate nicely in time), or
2. We pass the glob for the atomic dataset, and let cf-python do an internal cf.aggregate.

My contention is that 2 will be much slower, we should test this.

#### Outputs

I would like code to do the initial CFA creation, and code to do the updates. It is likely this will be suitable for a combination of python and slurm. We might want to put the slurm files in examples, and we certainly want to start generating some documenation on how to do these things. Documentation can go into a doc folder and should be in markdown.