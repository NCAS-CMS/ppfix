#!/usr/bin/env python3
"""
hdf5_metadata_block_size.py
============================
Computes a recommended metadata_block_size for an HDF5 file after rechunking,
based on h5stat output and the B-tree node size formula from the HDF5 spec.

Usage
-----
  # Parse h5stat output from a file:
  python hdf5_metadata_block_size.py --h5stat myfile.h5stat --scale 4

  # Run h5stat inline (requires h5stat on PATH):
  python hdf5_metadata_block_size.py --hdf5 myfile.h5 --scale 4

  # Override specific parameters:
  python hdf5_metadata_block_size.py --hdf5 myfile.h5 --scale 4 --ik 64 --margin 1.5

  # Print breakdown details:
  python hdf5_metadata_block_size.py --hdf5 myfile.h5 --scale 4 --verbose

Background
----------
When rechunking an HDF5 file, the B-tree index for each chunked dataset grows
proportionally with the number of chunks.  The fixed metadata (superblock,
object headers, group trees, heaps) stays roughly constant.  This tool:

  1. Reads h5stat output to extract:
       - Total metadata size
       - Per-dataset chunk counts and dimensionality

  2. Estimates the current B-tree footprint from the spec formula.

  3. Computes the expected B-tree footprint after rechunking.

  4. Returns:
       metadata_block_size = (fixed_metadata + new_btree) * margin
       rounded up to the next power of two (or --no-pow2 to disable).

B-tree node size formula (HDF5 spec, Type 1 v1 B-tree)
-------------------------------------------------------
  key_size  = 8 + 8 * N          (N = dataset dimensionality)
  node_size = 24 + (2*ik+1)*key_size + 2*ik*S
              where S = size-of-offsets (default 8, i.e. 64-bit file)
                    ik = istore_k (default 32, read from superblock)

  Effective fill factor ~75% on average (per HDF5 docs), so:
  fan_out = 2 * ik * 0.75   (for average case)
  fan_out = ik               (conservative / upper-bound node count)

  n_leaves   = ceil(n_chunks / fan_out)
  n_internal = ceil(n_leaves / fan_out)  [typically 1-2 levels]
  total_nodes = n_leaves + n_internal + 1  (root)
  btree_bytes = total_nodes * node_size
"""

import argparse
import math
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path



# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class DatasetInfo:
    """Metadata for a single HDF5 dataset (as parsed from h5stat)."""
    name: str
    n_chunks: int
    n_dims: int


@dataclass
class H5StatSummary:
    """Parsed summary of h5stat output."""
    total_metadata_bytes: int
    superblock_bytes: int
    datasets: list[DatasetInfo] = field(default_factory=list)
    ik: int = 32          # istore_k; read from superblock if available
    size_of_offsets: int = 8  # S; almost always 8 for modern files


# ---------------------------------------------------------------------------
# h5stat parsing
# ---------------------------------------------------------------------------

def run_h5stat(hdf5_path: str) -> str:
    """Run `h5stat -S -s <file>` and return stdout as a string."""
    try:
        result = subprocess.run(
            ["h5stat", "-S", "-s", hdf5_path],
            capture_output=True, text=True, check=True
        )
        return result.stdout
    except FileNotFoundError:
        sys.exit(
            "ERROR: h5stat not found on PATH.  "
            "Install HDF5 tools or supply --h5stat <output_file> instead."
        )
    except subprocess.CalledProcessError as e:
        sys.exit(f"ERROR: h5stat failed:\n{e.stderr}")


def parse_h5stat(text: str) -> H5StatSummary:
    """
    Parse the output of `h5stat -S -s`.

    h5stat -S prints per-dataset storage info; -s prints file-space summary.
    We pick out:
      - File metadata total  (from the file-space section)
      - Superblock size      (from the file-space section)
      - Per-dataset:         number of chunks, number of dimensions
    """
    summary = H5StatSummary(total_metadata_bytes=0, superblock_bytes=0)

    # ---- File-space section ------------------------------------------------
    # Example lines:
    #   File metadata: 123456 bytes
    #   Superblock: 96 bytes
    #   Indexed storage B-trees: 78900 bytes   ← not always present
    #   istore_k: 32                            ← not always present

    meta_match = re.search(r"File metadata:\s+(\d+)\s+bytes", text, re.I)
    if meta_match:
        summary.total_metadata_bytes = int(meta_match.group(1))

    sb_match = re.search(r"Superblock(?:\s+extension)?:\s+(\d+)\s+bytes", text, re.I)
    if sb_match:
        summary.superblock_bytes = int(sb_match.group(1))

    ik_match = re.search(r"Indexed\s+storage\s+(?:internal\s+node\s+)?K[:\s]+(\d+)", text, re.I)
    if ik_match:
        summary.ik = int(ik_match.group(1))

    soo_match = re.search(r"Size\s+of\s+offsets:\s+(\d+)", text, re.I)
    if soo_match:
        summary.size_of_offsets = int(soo_match.group(1))

    # ---- Per-dataset storage section  -------------------------------------
    # h5stat -S output per dataset looks like:
    #
    #   Dataset: /path/to/dataset
    #       ...
    #       Number of chunks: 512
    #       Dimension rank: 3
    #
    # The exact labels differ slightly between HDF5 versions; we match
    # several variants.

    # Split into per-dataset blocks by looking for "Dataset:" headers
    blocks = re.split(r"(?=^\s*Dataset\s*:)", text, flags=re.MULTILINE)

    for block in blocks:
        name_m = re.match(r"\s*Dataset\s*:\s*(.+)", block)
        if not name_m:
            continue
        name = name_m.group(1).strip()

        chunks_m = re.search(
            r"Number\s+of\s+chunks(?:\s+written)?:\s+(\d+)", block, re.I
        )
        dims_m = re.search(
            r"Dimension(?:ality)?\s+(?:rank|count)?:?\s*(\d+)", block, re.I
        )
        if not dims_m:
            # Fallback: count entries in "Chunk dimension sizes:" line
            cdim_m = re.search(r"Chunk\s+dimension\s+sizes?:\s+([\d\s]+)", block, re.I)
            if cdim_m:
                dims_m_val = len(cdim_m.group(1).split())
            else:
                dims_m_val = None
        else:
            dims_m_val = int(dims_m.group(1))

        if chunks_m and dims_m_val is not None:
            summary.datasets.append(DatasetInfo(
                name=name,
                n_chunks=int(chunks_m.group(1)),
                n_dims=int(dims_m_val),
            ))

    return summary


# ---------------------------------------------------------------------------
# B-tree size calculation (from HDF5 spec)
# ---------------------------------------------------------------------------

def btree_node_size(n_dims: int, ik: int = 32, S: int = 8) -> int:
    """
    Return the on-disk size in bytes of a single Type-1 v1 B-tree node
    used for chunk indexing.

    Node layout (HDF5 spec Level 1A1):
        Signature       : 4
        Node type       : 1
        Node level      : 1
        Entries used    : 2
        Left sibling    : S
        Right sibling   : S
        [Key, Child] * (2*ik)   then one final Key
        Key size        : 4 (chunk size) + 4 (filter mask) + N*8 (offsets)
        Child ptr size  : S
    """
    key_size = 8 + 8 * n_dims          # 4-byte chunk-size + 4-byte filter-mask + N×8-byte offsets
    node_header = 4 + 1 + 1 + 2 + S + S   # 8 + 2S fixed overhead
    n_keys = 2 * ik + 1                # one extra trailing key
    n_children = 2 * ik
    return node_header + n_keys * key_size + n_children * S


def btree_total_bytes(
    n_chunks: int,
    n_dims: int,
    ik: int = 32,
    S: int = 8,
    conservative: bool = False,
) -> int:
    """
    Estimate total B-tree metadata bytes for a dataset with n_chunks chunks.

    Parameters
    ----------
    n_chunks     : number of allocated chunks in the dataset
    n_dims       : dataset dimensionality
    ik           : istore_k (half the max entries per node); default 32
    S            : size_of_offsets in bytes; default 8
    conservative : if True use 50% fill (ik entries/node) instead of
                   the average 75% (1.5*ik entries/node).  Gives an
                   upper bound on node count.
    """
    if n_chunks == 0:
        return 0

    fan_out = ik if conservative else int(2 * ik * 0.75)  # entries per node
    fan_out = max(fan_out, 1)

    node_sz = btree_node_size(n_dims, ik, S)

    n_leaves   = math.ceil(n_chunks / fan_out)
    n_level1   = math.ceil(n_leaves  / fan_out)
    n_level2   = math.ceil(n_level1  / fan_out)
    # Root is counted within n_level1 when tree is 2-deep; add 1 for root
    # to be safe (negligible cost).
    total_nodes = n_leaves + n_level1 + n_level2 + 1
    return total_nodes * node_sz


def total_btree_bytes(datasets: list[DatasetInfo], ik: int, S: int,
                      conservative: bool = False) -> int:
    return sum(
        btree_total_bytes(ds.n_chunks, ds.n_dims, ik, S, conservative)
        for ds in datasets
    )


# ---------------------------------------------------------------------------
# Recommendation logic
# ---------------------------------------------------------------------------

def next_power_of_two(n: int) -> int:
    if n <= 0:
        return 1
    return 1 << (n - 1).bit_length()


def recommend_metadata_block_size(
    summary: H5StatSummary,
    scale: float,
    margin: float = 1.25,
    conservative: bool = False,
    pow2: bool = True,
    verbose: bool = False,
) -> int:
    """
    Return a recommended metadata_block_size (bytes) for the rechunked file.

    Strategy
    --------
      fixed_metadata = h5stat total - estimated current B-tree footprint
      new_btree      = B-tree estimate with n_chunks *= scale
      recommended    = (fixed_metadata + new_btree) * margin
                       rounded up to next power of two (if pow2=True)
    """
    ik = summary.ik
    S  = summary.size_of_offsets

    current_btree = total_btree_bytes(summary.datasets, ik, S, conservative)

    # Clamp so fixed never goes negative (e.g. if h5stat didn't give us all
    # dataset info and our estimate overshoots).
    fixed_metadata = max(summary.total_metadata_bytes - current_btree, 0)

    scaled_datasets = [
        DatasetInfo(
            name=ds.name,
            n_chunks=math.ceil(ds.n_chunks * scale),
            n_dims=ds.n_dims,
        )
        for ds in summary.datasets
    ]
    new_btree = total_btree_bytes(scaled_datasets, ik, S, conservative)

    raw = int((fixed_metadata + new_btree) * margin)
    result = next_power_of_two(raw) if pow2 else raw

    if verbose:
        print("\n── h5stat summary ─────────────────────────────────────────")
        print(f"  Total metadata (h5stat)  : {summary.total_metadata_bytes:>12,} bytes")
        print(f"  Superblock               : {summary.superblock_bytes:>12,} bytes")
        print(f"  istore_k                 : {ik}")
        print(f"  Size of offsets (S)      : {S} bytes")
        print(f"  Chunked datasets found   : {len(summary.datasets)}")
        for ds in summary.datasets:
            nb = btree_node_size(ds.n_dims, ik, S)
            print(f"    {ds.name}")
            print(f"      dims={ds.n_dims}  chunks={ds.n_chunks:,}"
                  f"  node_size={nb} bytes")

        print("\n── B-tree estimates ────────────────────────────────────────")
        print(f"  Current B-tree (est.)    : {current_btree:>12,} bytes"
              f"  ({'conservative' if conservative else 'average-fill'})")
        print(f"  Fixed metadata (derived) : {fixed_metadata:>12,} bytes")
        print(f"  Scale factor             : {scale}×")
        print(f"  New B-tree (est.)        : {new_btree:>12,} bytes")
        print(f"  Margin                   : {margin}×")
        print(f"  Raw recommendation       : {raw:>12,} bytes")
        if pow2:
            print(f"  Rounded to next pow-2    : {result:>12,} bytes  ← use this")
        print("────────────────────────────────────────────────────────────\n")

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Recommend HDF5 metadata_block_size after rechunking.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument(
        "--hdf5", metavar="FILE",
        help="Path to HDF5 file; h5stat is run automatically."
    )
    src.add_argument(
        "--h5stat", metavar="FILE",
        help="Path to pre-captured h5stat output (text file)."
    )
    p.add_argument(
        "--scale", type=float, default=4.0,
        help="Chunk-count multiplication factor after rechunking (default: 4)."
    )
    p.add_argument(
        "--ik", type=int, default=None,
        help="Override istore_k (default: read from h5stat or use 32)."
    )
    p.add_argument(
        "--margin", type=float, default=1.25,
        help="Safety margin multiplier (default: 1.25)."
    )
    p.add_argument(
        "--conservative", action="store_true",
        help="Use 50%% fill factor instead of 75%% (upper-bound node count)."
    )
    p.add_argument(
        "--no-pow2", action="store_true",
        help="Do not round result up to the next power of two."
    )
    p.add_argument(
        "--verbose", "-v", action="store_true",
        help="Print full breakdown."
    )
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)

    if args.hdf5:
        h5stat_text = run_h5stat(args.hdf5)
    else:
        h5stat_text = Path(args.h5stat).read_text()

    summary = parse_h5stat(h5stat_text)

    if not summary.total_metadata_bytes:
        print(
            "WARNING: could not parse total metadata size from h5stat output.\n"
            "         Only B-tree estimate will be used.",
            file=sys.stderr,
        )

    if not summary.datasets:
        print(
            "WARNING: no chunked dataset info found in h5stat output.\n"
            "         Run h5stat with -S flag for per-dataset storage stats.\n"
            "         Falling back to B-tree estimate of 0.",
            file=sys.stderr,
        )

    if args.ik is not None:
        summary.ik = args.ik

    result = recommend_metadata_block_size(
        summary,
        scale=args.scale,
        margin=args.margin,
        conservative=args.conservative,
        pow2=not args.no_pow2,
        verbose=args.verbose,
    )

    if args.verbose:
        print(f"Recommended metadata_block_size: {result:,} bytes  ({result // 1024} KiB)\n")
    else:
        print(result)


# ---------------------------------------------------------------------------
# Minimal self-test (run with: python hdf5_metadata_block_size.py --selftest)
# ---------------------------------------------------------------------------

def selftest():
    """Quick sanity checks against hand-calculated values."""
    # Node size: 1D, ik=32, S=8
    # key=16, node = 24 + 65*16 + 64*8 = 24+1040+512 = 1576
    assert btree_node_size(1, 32, 8) == 1576, btree_node_size(1, 32, 8)
    assert btree_node_size(2, 32, 8) == 2096
    assert btree_node_size(3, 32, 8) == 2616

    # For 1 chunk: 1 leaf + 1 internal (=root) + 0 level2 + 1 extra root = 3 nodes
    b = btree_total_bytes(1, 1, ik=32, S=8, conservative=False)
    assert b > 0

    # Scaling: 4x chunks → roughly 4x B-tree bytes (leaves dominate)
    b1 = btree_total_bytes(1000, 2, ik=32, S=8)
    b4 = btree_total_bytes(4000, 2, ik=32, S=8)
    ratio = b4 / b1
    assert 3.5 < ratio < 4.5, f"Expected ~4x scaling, got {ratio:.2f}x"

    print("All self-tests passed.")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        main()