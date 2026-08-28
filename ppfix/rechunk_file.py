import cf
import time
from uuid import uuid4

from ppfix.utils import meta2attr
from ppfix.chunking import get_nemochunking

def rechunk_existing_netcdf(filename, outfilename, metadata, section, kwchoices):
    """
    Rechunk an existing netCDF file with the specified properties and chunk sizes.

    Parameters:
    - filename: Path to the existing netCDF file.
    - outfilename: Path where the rechunked netCDF file will be saved.
    - metadata: Metadata configuration.
    - section: Section of the metadata to use for properties.   
    - chunks: Tuple specifying the new chunk sizes.
    - kwchoices: Additional keyword arguments for the cf.write function.

    Returns:
    - None
    """

    if section in ['model_ocean', 'model_seaice']:
        chunk_algorithm = get_nemochunking
    else:
        raise ValueError(f"Unsupported section '{section}' for rechunking.")

  
    t1 = time.perf_counter()
    fields = cf.read(str(filename))
    tr = time.perf_counter() - t1
    print(f'Time to read [{filename}] took {tr:.2f} seconds')
    tracking_id = str(uuid4())
    ta = time.perf_counter()
    for v in fields:
        meta2attr(metadata, v, section)
        chunks = chunk_algorithm(v)
        if chunks is not None:
            v.nc_set_dataset_chunksizes(tuple(chunks))
            v.data.rechunk(tuple(chunks), inplace=True)
        if not hasattr(v, 'tracking_id'):
            v.set_property('tracking_id', tracking_id)
        
    cf.write(fields, str(outfilename), **kwchoices)
    t2 = time.perf_counter() - ta
    print(f'Total time for chunking {filename} was {t2:.2f} seconds')
    