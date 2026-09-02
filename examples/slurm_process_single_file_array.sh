#!/bin/bash
#SBATCH --job-name=ppfix_file
#SBATCH --partition=standard
#SBATCH --time=12:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=24G
#SBATCH --output=slurm-out/ppfix_%A_%a.out
#SBATCH --error=slurm-out/ppfix_%A_%a.err
#SBATCH --account=hiresgw
#SBATCH --qos=standard

# Use one array task per input file.
# Example submission:
#   sbatch --array=0-$(($(wc -l < file-manifest.txt) - 1)) \
#     SCRIPT_DIR MANIFEST_FILE OUTPUT_DIRECTORY METADATA_FILE
#   Example:
#     sbatch --array=0-$(($(wc -l < file-manifest.txt) - 1)) \
#     "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)" \ 
#     file-manifest.txt /path/to/output experiment_configs/n1280o12.conf

set -euo pipefail

source "$(conda info --base)/etc/profile.d/conda.sh"
mamba activate ppfix

if [[ $# -lt 3 ]]; then
    echo "Usage: $0 MANIFEST_FILE OUTPUT_DIRECTORY METADATA_FILE" >&2
    exit 1
fi

SCRIPT_DIR=$1
MANIFEST_FILE=$2
OUTPUT_DIRECTORY=$3
METADATA_FILE=$4


INPUT_FILE=$(sed -n "$((SLURM_ARRAY_TASK_ID + 1))p" "$MANIFEST_FILE")

if [[ -z "$INPUT_FILE" ]]; then
    echo "No input file found for SLURM_ARRAY_TASK_ID=$SLURM_ARRAY_TASK_ID" >&2
    exit 1
fi

python -u "$SCRIPT_DIR/process_single_file.py" "$INPUT_FILE" "$OUTPUT_DIRECTORY" "$METADATA_FILE"