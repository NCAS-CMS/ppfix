import cf
import time

from fragmentation import check_fragmentation

def rechunk_existing_netcdf(filename, outfilename, properties, kwchoices, chunks):
    """
    Rechunk an existing netCDF file with the specified properties and chunk sizes.

    Parameters:
    - filename: Path to the existing netCDF file.
    - outfilename: Path where the rechunked netCDF file will be saved.
    - properties: Dictionary of properties to set on the variables.
    - chunks: Tuple specifying the new chunk sizes.
    - kwchoices: Additional keyword arguments for the cf.write function.

    Returns:
    - None
    """
  

    t1 = time.perf_counter()
    fields = cf.read(str(filename))
    tr = time.perf_counter() - t1
    print(f'Time to read [{filename}] took {tr:.2f} seconds')

    for v in fields:
        ta = time.perf_counter()
        cs = v.nc_dataset_chunksizes()
        existing_chunks = list(cs)
        grid_metadata = properties.get('grid', '') + f'{existing_chunks[-1]}x{existing_chunks[-2]}'
        new_chunks = list(cs)
        new_chunks[-2:] = chunks
        print('Existing chunks:', existing_chunks, '  New chunks:', new_chunks)

        v.nc_set_dataset_chunksizes(tuple(new_chunks))
        v.data.rechunk(tuple(new_chunks), inplace=True)
        tb = time.perf_counter() - ta
        print(f'Preparing rechunking for [{v.identity()}]({v.data.shape}) took {tb:.2f} seconds')
        properties['grid'] = grid_metadata
        for k, vv in properties.items():
            if isinstance(vv, list):
                vv = ','.join(vv)
            v.set_property(k, vv)

    cf.write(fields, str(outfilename), **kwchoices)
    t2 = time.perf_counter() - t1
    print(f'Total time for chunking {filename} with {chunks} was {t2:.2f} seconds')
    fragmentation = check_fragmentation(str(outfilename))
    if fragmentation:
        print(f'Warning: The rechunked file [{outfilename}] is fragmented.')
    