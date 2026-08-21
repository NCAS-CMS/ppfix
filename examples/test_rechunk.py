import cf
import contextlib
import time
from pathlib import Path
from postproc.fragmentation import check_fragmentation

from postproc.rechunk_file import rechunk_existing_netcdf


TEST_FILE = '~/data/Lawrence4TB/u-dz876/NEMO/dz876o_1d_19500101_19500101_grid_T.nc'
TEST_FILE = Path(TEST_FILE).expanduser()

O12Expected = (4322, 3606)

CHUNK_OPTIONS = [
     
    (1024, 1024),
    #(512, 512),
    #(2166, 1803),
    (1083, 601),
]

KWCHOICES = {'single': True,
             'h5py_options': {'meta_block_size': 1024 * 1024}
}

def test_rechunking():
    """
    Test the rechunking functionality by utilising an existing file, rechunking it with
    some new chunk sizes, and verifying that the chunk sizes have been updated correctly,
    and in doing so, generate some benchmarking around chunking.
    """
 
    with open('test_results.txt', 'w') as f:

        for CHUNKING in CHUNK_OPTIONS:
            f.write(f'\nTesting rechunking with chunk sizes: {CHUNKING}\n')
            f.write('-' * 50 + '\n')
            f.flush()

            # Call the rechunk_existing_netcdf function with the test file and new chunk sizes
            test_path = Path(TEST_FILE)
            out_file = test_path.with_name(
                f"{test_path.stem}_rechunked_{CHUNKING[0]}x{CHUNKING[1]}{test_path.suffix}"
            )
            print('Writing to ', out_file)
            p1 = time.perf_counter()
            with contextlib.redirect_stdout(f):
                rechunk_existing_netcdf(TEST_FILE, out_file, properties={'grid': 'test_grid'}, kwchoices=KWCHOICES, chunks=CHUNKING)
            f.flush()
            p2 = time.perf_counter() - p1
            f.write(f'Total time for rechunking with chunk sizes {CHUNKING} took {p2:.2f} seconds\n')
            f.write('-' * 50 + '\n\n')

            # Read the rechunked file and verify the chunk sizes
            fields = cf.read(str(out_file))
            for v in fields:
                new_chunks = v.nc_dataset_chunksizes()
                assert new_chunks[-2:] == CHUNKING, f"Expected chunks {CHUNKING}, but got {new_chunks[-2:]}"
            assert not check_fragmentation(out_file), f"The rechunked file {out_file} is fragmented."

         

