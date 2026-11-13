#!/bin/bash
set -euo pipefail

source "$(conda info --base)/etc/profile.d/conda.sh"
mamba activate ppfix

if [[ $# -lt 3 ]]; then
    echo "Usage: $0 INPUT_DIRECTORY OUTPUT_DIRECTORY METADATA_FILE" >&2
    exit 1
fi

INPUT_DIRECTORY=$1
OUTPUT_DIRECTORY=$2
METADATA_FILE=$3

expand_path() {
    python -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).expanduser())' "$1"
}

INPUT_DIRECTORY=$(expand_path "$INPUT_DIRECTORY")
OUTPUT_DIRECTORY=$(expand_path "$OUTPUT_DIRECTORY")
METADATA_FILE=$(expand_path "$METADATA_FILE")

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
MANIFEST_FILE="$OUTPUT_DIRECTORY/file-manifest.txt"

mkdir -p "$OUTPUT_DIRECTORY" slurm-out

python -u "$SCRIPT_DIR/generate_manifest.py" "$INPUT_DIRECTORY" "$MANIFEST_FILE"

TASKS=$(wc -l < "$MANIFEST_FILE" | tr -d ' ')
if [[ "$TASKS" -eq 0 ]]; then
    echo "No input files found in $INPUT_DIRECTORY" >&2
    exit 1
fi

SBATCH_ARGS=(
    --array="0-$((TASKS - 1))"
    "$SCRIPT_DIR/slurm_process_single_file_array.sh"
    "$SCRIPT_DIR"
    "$MANIFEST_FILE"
    "$OUTPUT_DIRECTORY"
    "$METADATA_FILE"
)

sbatch "${SBATCH_ARGS[@]}"