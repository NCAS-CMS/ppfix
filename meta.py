from pathlib import Path
import math
import re
import shutil
import subprocess


def extract_metadata_bytes(h5stat_output):
    """Return the 'File metadata' byte count from h5stat output."""
    # We are looking for the line with File metadata size, which is the end of the output
    # in a block that looks like:
    # Summary of file space information:
    #   File metadata: 199777 bytes
    #   Raw data: 1870247684 bytes
    #   Amount/Percent of tracked free space: 0 bytes/0.0%
    #   Unaccounted space: 11849 bytes
    # Total space: 1870459310 bytes
    match = re.search(
        r"^\s*File metadata(?: size)?:\s*([\d,]+)\s*bytes\b",
        h5stat_output,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    if not match:
        raise ValueError("Could not find 'File metadata' bytes in h5stat output.")

    return int(match.group(1).replace(",", ""))


def extract_chunk_index_bytes(h5stat_output):
    """Return the chunk-index metadata bytes from the h5stat report."""
    match = re.search(
        r"Chunked datasets:\s*(?:\n.+?)*?^\s*Index:\s*([\d,]+)\s*$",
        h5stat_output,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    if not match:
        raise ValueError("Could not find chunk-index bytes in h5stat output.")

    return int(match.group(1).replace(",", ""))


def run_h5stat(ncfile):
    """Run h5stat and return the full command output as text."""
    ncfile = Path(ncfile).expanduser()
    if not ncfile.exists():
        raise FileNotFoundError(f"File {ncfile} does not exist.")

    if shutil.which("h5stat") is None:
        raise RuntimeError(
            "h5stat was not found in PATH. Install HDF5 tools and retry."
        )

    result = subprocess.run(
        ["h5stat", str(ncfile)],
        capture_output=True,
        text=True,
        check=False,
    )
    h5stat_output = (result.stdout or "") + (result.stderr or "")

    if result.returncode != 0:
        raise RuntimeError(
            f"h5stat failed with exit code {result.returncode}:\n{h5stat_output}"
        )

    return h5stat_output


def h5analyse(ncfile):
    """Run h5stat on the specified file and return total metadata bytes."""
    h5stat_output = run_h5stat(ncfile)
    metadata = extract_metadata_bytes(h5stat_output)

    return metadata


def chunk_count_growth_factor(existing_chunk_shape, new_chunk_shape):
    """Estimate chunk-count growth from old/new chunk shapes."""
    old_shape = tuple(int(v) for v in existing_chunk_shape)
    new_shape = tuple(int(v) for v in new_chunk_shape)

    if len(old_shape) != len(new_shape):
        raise ValueError("existing_chunk_shape and new_chunk_shape must have the same rank")
    if not old_shape:
        raise ValueError("Chunk shapes must not be empty")
    if any(v <= 0 for v in old_shape + new_shape):
        raise ValueError("Chunk dimensions must all be > 0")

    old_chunk_elements = math.prod(old_shape)
    new_chunk_elements = math.prod(new_shape)
    return old_chunk_elements / new_chunk_elements

def metablock_heuristic(
    existing_file,
    existing_chunk_shape,
    new_chunk_shape,
    headroom_factor=1.25,
    block_quantum=32*1024,
):
    """Estimate new metadata size from a chunk-shape change.

    The estimate splits current metadata into fixed metadata plus chunk-index
    metadata, scales the chunk-index component by the implied chunk-count growth,
    then applies optional headroom and optional rounding.

    Parameters
    ----------
    existing_file : str or pathlib.Path
        Path to an existing NetCDF/HDF5 file that `h5stat` can analyse.
    existing_chunk_shape : tuple[int, ...]
        Current chunk shape used as the baseline.
    new_chunk_shape : tuple[int, ...]
        Proposed chunk shape to estimate against.
    headroom_factor : float, optional
        Multiplicative safety margin applied to the estimated metadata bytes.
        Must be >= 1. Default is 1.25.
    block_quantum : int or None, optional
        If provided, round the final estimate up to the nearest multiple of this
        value (for example 4096). Must be > 0 when set. Default is 32*1024.

    Returns
    -------
    int
        Estimated metadata size in bytes after applying optional headroom and
        optional rounding.
    """
    file_path = Path(existing_file).expanduser()
    if not file_path.exists():
        raise FileNotFoundError(f"Input file does not exist: {file_path}")
    if headroom_factor < 1:
        raise ValueError("headroom_factor must be >= 1")
    if block_quantum is not None and block_quantum <= 0:
        raise ValueError("block_quantum must be > 0 when provided")

    chunk_growth_factor = chunk_count_growth_factor(
        existing_chunk_shape,
        new_chunk_shape,
    )

    h5stat_output = run_h5stat(file_path)
    existing_metadata_bytes = extract_metadata_bytes(h5stat_output)
    chunk_index_bytes = extract_chunk_index_bytes(h5stat_output)
    fixed_metadata_bytes = max(existing_metadata_bytes - chunk_index_bytes, 0)

    estimated_chunk_index_bytes = int(round(chunk_index_bytes * chunk_growth_factor))
    estimated_metadata_bytes = fixed_metadata_bytes + estimated_chunk_index_bytes

    estimated_metadata_bytes = int(math.ceil(estimated_metadata_bytes * headroom_factor))
    if block_quantum is not None:
        estimated_metadata_bytes = int(
            math.ceil(estimated_metadata_bytes / block_quantum) * block_quantum
        )

    return estimated_metadata_bytes







