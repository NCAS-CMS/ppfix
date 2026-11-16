# Analysing Slurm array failures

Use the ppfix environment and the same working directory used to submit the
array, where the example writes logs under `slurm-out/`. Record the array job ID
printed by `sbatch` and identify the matching timestamped manifest in the output
directory. The tool cannot verify that the job ID and manifest match.

Check Slurm's recorded task states and exit codes:

```console
sacct -j ARRAY_JOB_ID --format=JobID,State,ExitCode
```

After the array has finished, analyse its logs with:

```console
python examples/find_failed_array_tasks.py slurm-out /path/to/manifest.txt \
  --job-id ARRAY_JOB_ID \
  --report-file slurm-out/failed-tasks-ARRAY_JOB_ID.csv \
  --failed-manifest-file slurm-out/failed-file-manifest-ARRAY_JOB_ID.txt
```

Use distinct report paths: existing output files are overwritten. The CSV lists
job and task IDs, mapped inputs, log paths and the first non-empty stderr line.
The failed manifest contains mapped inputs, one per line. Task IDs are zero-based;
an out-of-range task has a blank CSV input and is omitted from the manifest.

The collector flags non-empty `.err` files, not Slurm exit codes: warnings may
be flagged, while failures with empty or missing stderr are missed. Review
`sacct` and the full logs. Correct the cause and review the retry manifest before
submitting it; check existing outputs first because reruns can encounter or
replace them.
