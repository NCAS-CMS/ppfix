from ppfix.inventory import inventory
from ppfix.fix_atmosphere import process_atmos
from ppfix.process_nemo import process_ocean
from ppfix.process_nemo import process_sice
from pathlib import Path
import configparser

TARGET = '/Volumes/Lawrence4TB/u-dz876/'
METADATADIR = Path(__file__).parent.parent / 'experiment_configs'
METADATA = METADATADIR / 'n1280o12.conf'
RUNID = 'udz876'

AOUT = '/Volumes/Lawrence4TB/u-dz876/'+'atmos'
OOUT = '/Volumes/Lawrence4TB/u-dz876/'+'nemo'
SIOUT = '/Volumes/Lawrence4TB/u-dz876/'+'sice'

if not Path.exists(METADATA):
    raise FileNotFoundError(f'Metadata file {METADATA} does not exist.')

metadata = configparser.ConfigParser(interpolation=None)
metadata.read(METADATA)

#inventory('hrcm_n1280o12_control', TARGET, inv_file=Path(__file__).parent / 'inventory_test.txt')
process_atmos(TARGET, AOUT, metadata, 'model_atmos')
process_ocean(TARGET, OOUT, metadata, 'model_ocean')
process_sice(TARGET, SIOUT, metadata, 'model_seaice')




