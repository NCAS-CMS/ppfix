import configparser
from pathlib import Path


from ppfix.rechunk_file import rechunk_existing_netcdf
from ppfix.utils import meta2output, build_simulation_name

def new_name(filename: str, origin, simulation: str) -> str:
    parts = filename.split('_')
    return f"{simulation.lower()}_{origin}_{'_'.join(parts[2:])}"


def process_ocean(
    nemo_folder: str,
    target_folder: str,
    metadata: configparser.ConfigParser,
    REPLACE: bool = False,
):
    """
    Process NEMO ocean files by rechunking them and adding metadata.

    Parameters:
        nemo_folder (str): Path to the folder containing NEMO files.
        target_folder (str): Path to the folder where processed files will be saved.
        metadata (configparser.ConfigParser): Metadata configuration.
        REPLACE (bool): If True, replace existing files in target folder. If False, skip existing files.
    """


    input_folder = Path(nemo_folder)
    output_folder = Path(target_folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    files = input_folder.glob('nemo*.nc')

    kwchoices = meta2output(metadata)

    simulation = build_simulation_name(metadata)
    for f in files:
        print('Examining: ',f)
        target_file = output_folder / new_name(f.name, 'ocean', simulation)
        if target_file.exists() and not REPLACE:
            print(f'Skipping {f}, target file {target_file} already exists and REPLACE is False.')
            continue
        rechunk_existing_netcdf(f, target_file, metadata, 'model_ocean', 
                                kwchoices=kwchoices)

    
def process_sice(
    sice_folder: str,
    target_folder: str,
    metadata: configparser.ConfigParser,
    REPLACE: bool = False,
):
    """
    Process NEMO sea ice files by rechunking them and adding metadata.

    Parameters:
        sice_folder (str): Path to the folder containing sea ice files.
        target_folder (str): Path to the folder where processed files will be saved.
        metadata (configparser.ConfigParser): Metadata configuration.
        REPLACE (bool): If True, replace existing files in target folder. If False, skip existing files.
    """

    input_folder = Path(sice_folder)
    output_folder = Path(target_folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    files = input_folder.glob('si3*.nc')

    kwchoices = meta2output(metadata)

    simulation = build_simulation_name(metadata)
    for f in files:
        print('Examining: ',f)
        target_file = output_folder / new_name(f.name, 'sice', simulation)
        if target_file.exists() and not REPLACE:
            print(f'Skipping {f}, target file {target_file} already exists and REPLACE is False.')
            continue
        rechunk_existing_netcdf(f, target_file, metadata, 'model_seaice', kwchoices=kwchoices)
    
