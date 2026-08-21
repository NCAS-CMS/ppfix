from ppfix.inventory import inventory
from ppfix.fix_atmosphere import process_atmos
from pathlib import Path
import configparser
import os

TARGET = '/Volumes/Lawrence4TB/u-dz876/'
METADATADIR = Path(__file__).parent.parent / 'experiment_configs'
METADATA = METADATADIR / 'n1280o12.conf'
RUNID = 'udz876'

if not Path.exists(METADATA):
    raise FileNotFoundError(f'Metadata file {METADATA} does not exist.')

metadata = configparser.ConfigParser(interpolation=None)
metadata.read(METADATA)

#inventory('hrcm_n1280o12_control', TARGET, inv_file=Path(__file__).parent / 'inventory_test.txt')
process_atmos(TARGET,TARGET+'/atmos', metadata, 'model_atmos')




