import time
import cf
import json5
from pathlib import Path

from rechunk_file import rechunk_existing_netcdf

###### USER CONFIGURATION 

kwchoices = {'single': True,
             'h5py_options':{'meta_block_size': 1024*1024,},
             }

NEMO_FOLDER = '~/data/Lawrence4TB/u-dz876/NEMO'
TARGET_FOLDER = '~/data/Lawrence4TB/u-dz876/NEMO_rechunked'

# There doesn't appear to be a good solution for NEMO. 
# This one should minimise chunks read per basin and results in 
# an acceptable number of edge chunks.
NEMO_CHUNKS = (1024,1024)

nemo_folder = Path(NEMO_FOLDER).expanduser()
target_folder = Path(TARGET_FOLDER).expanduser()
metadata_file = Path(__file__).parent / 'metadata.jsonc'

REPLACE = False  # If True, will replace existing files in target folder. If False, will skip them.

##### END CONFIGURATION


parts = nemo_folder.parts
runid = parts[-3]


metadata = json5.load(metadata_file.open())

metadata['run_specific']['runid'] = runid
files = nemo_folder.glob('*.nc')
dlines = metadata.pop('descriptionLines')
metadata['description'] = '\n'.join(dlines)

output_metadata = {k:v for k,v in metadata['HRCM General'].items()}
output_metadata['description'] = metadata['description']

if runid in metadata['run_specific']['variant_id']:
    output_metadata['variant_id'] = metadata['run_specific']['variant_id'][runid]

for f in files:
    print('Examining: ',f)
    target_file = target_folder / f.name
    target_file.parent.mkdir(parents=True, exist_ok=True)
    if target_file.exists() and not REPLACE:
        print(f'Skipping {f.name} as it already exists in target folder')
        continue
    
    t1 = time.perf_counter()
    fields = cf.read(str(f))
    tr = time.perf_counter() - t1
    print(f'Time to read [{f.name}] took {tr:.2f} seconds')
    for v in fields:
        ta = time.perf_counter()
        cs = v.nc_dataset_chunksizes()
        ncs = list(cs)
        grid_metadata = metadata['variable_specific']['grid'] + f'{ncs[-1]}x{ncs[-2]}'
        ncs[-2:] = NEMO_CHUNKS
        v.nc_dataset_chunksizes = tuple(ncs)
        v.data.rechunk(tuple(ncs), inplace=True)
        tb = time.perf_counter() - ta
        print(f'Preparing rechunking for [{v.identity()}]({v.data.shape}) took {tb:.2f} seconds')
        output_metadata['grid'] = grid_metadata
        for k,vv in output_metadata.items():
            if isinstance(vv, list):
                vv = ','.join(vv)
            v.set_property(k, vv)
    target_file = target_folder / f.name
    target_file.parent.mkdir(parents=True, exist_ok=True)
    cf.write(fields, str(target_file), **kwchoices)
    t2 = time.perf_counter() - t1
    print(f'Total time for {f} took {t2:.2f} seconds')
    print(fields)