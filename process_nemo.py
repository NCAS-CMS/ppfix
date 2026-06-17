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
# an acceptable number of edge chunks (all in one dimension),
# not that the dimensions are obvious in the tripolar world.
O12CHUNKS = (1660,601) #o12 grid is 4322x3606, so this results in 3x6 chunks, which is acceptable.

nemo_folder = Path(NEMO_FOLDER).expanduser()
target_folder = Path(TARGET_FOLDER).expanduser()
metadata_file = Path(__file__).parent / 'metadata.jsonc'

REPLACE = True  # If True, will replace existing files in target folder. If False, will skip them.

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
        print(f'Skipping {f}, target file {target_file} already exists and REPLACE is False.')
        continue
    rechunk_existing_netcdf(f, target_file, output_metadata, kwchoices, O12CHUNKS)    
    
   
