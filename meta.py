from pathlib import Path
import math
import re
import shutil
import subprocess

import cf


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


def _chunk_count(shape, chunks):
    """Return exact chunk count for a dataset shape/chunk layout."""
    if len(shape) != len(chunks):
        raise ValueError("shape and chunks must have the same rank")
    return math.prod(math.ceil(int(s) / int(c)) for s, c in zip(shape, chunks))


def _properties_size_bytes(properties):
    """Estimate byte size of properties once serialized as strings."""
    if not properties:
        return 0

    total = 0
    for key, value in properties.items():
        vv = value
        if isinstance(vv, list):
            vv = ",".join(str(item) for item in vv)
        total += len(str(key).encode("utf-8"))
        total += len(str(vv).encode("utf-8"))
    return total


def _exact_chunk_totals(existing_file, new_chunk_shape, chunk_shape_order="xy"):
    """Compute exact existing/new total chunk counts over rechunked fields."""
    if chunk_shape_order not in {"xy", "yx"}:
        raise ValueError("chunk_shape_order must be 'xy' or 'yx'")

    new_chunk_shape = tuple(int(v) for v in new_chunk_shape)
    if len(new_chunk_shape) != 2:
        raise ValueError("new_chunk_shape must have exactly 2 elements for X/Y rechunking")

    if chunk_shape_order == "xy":
        new_x, new_y = new_chunk_shape
    else:
        new_y, new_x = new_chunk_shape

    fields = cf.read(str(existing_file))
    old_total = 0
    new_total = 0

    for field in fields:
        # Match rechunk_file intent: rechunk data variables in X/Y only.
        try:
            field.coord("X")
            field.coord("Y")
        except Exception:
            continue

        current_chunks = field.nc_dataset_chunksizes()
        if current_chunks is None:
            continue

        shape = tuple(int(s) for s in field.data.shape)
        current_chunks = tuple(int(c) for c in current_chunks)
        if len(shape) != len(current_chunks):
            continue

        updated_chunks = current_chunks
        if len(current_chunks) >= 2:
            # Dataset storage order is ... , Y, X for trailing horizontal dims.
            updated_chunks = current_chunks[:-2] + (new_y, new_x)

        old_total += _chunk_count(shape, current_chunks)
        new_total += _chunk_count(shape, updated_chunks)

    if old_total == 0:
        raise ValueError("No rechunkable chunked fields were found for chunk counting")

    return old_total, new_total

def metablock_heuristic(
    existing_file,
    existing_chunk_shape,
    new_chunk_shape,
    chunk_shape_order="xy",
    properties=None,
    headroom_factor=1.25,
    block_quantum=32*1024,
):
    """Estimate new metadata size from exact chunk counts and property bytes.

    The estimate splits current metadata into fixed metadata plus chunk-index
    metadata, computes exact old/new chunk totals for rechunked data fields,
    scales chunk-index bytes using the old/new chunk totals, adds a simple
    properties budget (`2 * properties_bytes`), then applies optional headroom
    and optional rounding.

    Parameters
    ----------
    existing_file : str or pathlib.Path
        Path to an existing NetCDF/HDF5 file that `h5stat` can analyse.
    existing_chunk_shape : tuple[int, ...]
        Kept for compatibility with the previous API.
    new_chunk_shape : tuple[int, ...]
        Proposed chunk shape to estimate against.
    chunk_shape_order : {"xy", "yx"}, optional
        Order of values in `new_chunk_shape`. Default is "xy".
    properties : dict or None, optional
        Properties that will be set when writing the output. The heuristic adds
        `2 * serialized_properties_bytes` to the estimate.
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

    _ = existing_chunk_shape  # Kept for API compatibility; exact counts come from file.

    h5stat_output = run_h5stat(file_path)
    existing_metadata_bytes = extract_metadata_bytes(h5stat_output)
    chunk_index_bytes = extract_chunk_index_bytes(h5stat_output)
    fixed_metadata_bytes = max(existing_metadata_bytes - chunk_index_bytes, 0)

    old_total_chunks, new_total_chunks = _exact_chunk_totals(
        file_path,
        new_chunk_shape,
        chunk_shape_order=chunk_shape_order,
    )
    bytes_per_chunk = chunk_index_bytes / old_total_chunks
    estimated_chunk_index_bytes = int(math.ceil(bytes_per_chunk * new_total_chunks))

    # Add a simple budget for per-variable property metadata writes.
    properties_budget_bytes = 2 * _properties_size_bytes(properties)

    estimated_metadata_bytes = (
        fixed_metadata_bytes + estimated_chunk_index_bytes + properties_budget_bytes
    )

    estimated_metadata_bytes = int(math.ceil(estimated_metadata_bytes * headroom_factor))
    if block_quantum is not None:
        estimated_metadata_bytes = int(
            math.ceil(estimated_metadata_bytes / block_quantum) * block_quantum
        )

    return estimated_metadata_bytes







