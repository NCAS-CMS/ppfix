from pathlib import Path
from meta import metablock_heuristic

FOLDER = '~/data/Lawrence4TB/u-dz876/NEMO'
FILES = ['dz876o_1d_19500101_19500101_grid_T.nc', 'dz876o_1d_19500101_19500131_grid_T.nc',] 
EXPECTED_CHUNK_SHAPE = (1660, 601)  # Example new chunk shape for testing
EXISTING_CHUNK_SHAPE = (4322, 3606)  # Example existing chunk shape for testing

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
