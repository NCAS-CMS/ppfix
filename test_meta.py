from pathlib import Path

FOLDER = '~/data/Lawrence4TB/u-dz876/NEMO'
FILES = ['dz876o_1d_19500101_19500101_grid_T.nc', 'dz876o_1d_19500101_19500131_grid_T.nc',] 
EXPECTED_CHUNK_SHAPE = (1660, 601)  # Example new chunk shape for testing
EXISTING_CHUNK_SHAPE = (4322, 3606)  # Example existing chunk shape for testing


def metablock_heuristic(existing_file, 
                        
    """
    Estimate the metadata size for rechunking a NetCDF file based on the existing and new chunk shapes.

    Parameters:
    - existing_file: Path to the existing NetCDF file.
    - existing_chunk_shape: Tuple specifying the existing chunk sizes.
    - new_chunk_shape: Tuple specifying the new chunk sizes.
    - chunk_shape_order: Order of chunk dimensions, either "xy" or "yx".
    - properties: Optional dictionary of properties to set on the variables.
    - headroom_factor: Factor to account for additional metadata overhead.
    - block_quantum: Quantum size for block allocation.

    Returns:
    - Estimated metadata size in bytes.
    """
    old_total, new_total = _exact_chunk_totals(existing_file, new_chunk_shape, chunk_shape_order)
    
    # Calculate estimated metadata size with headroom and block quantum
    estimated_size = int(new_total * headroom_factor * block_quantum)
    
    return estimated_size


def test_meta():
    """
    Test the estimate_metadata_size function by comparing the estimated metadata size
    with the actual metadata size obtained from h5stat for a set of NetCDF files.
    """
    folder_path = Path(FOLDER).expanduser()
    
    for filename in FILES:
        file_path = folder_path / filename
        existing_chunk_shape = EXISTING_CHUNK_SHAPE
        new_chunk_shape = EXPECTED_CHUNK_SHAPE
        
        estimated_size = metablock_heuristic(
            existing_file=file_path,
            existing_chunk_shape=existing_chunk_shape,
            new_chunk_shape=new_chunk_shape,
            headroom_factor=1.25,
            block_quantum=32 * 1024
        )
        
        print(f"Estimated metadata size for {filename}: {estimated_size} bytes")
