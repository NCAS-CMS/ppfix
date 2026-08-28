import argparse
import configparser
from ppfix.fix_atmosphere import process_atmos
from ppfix.process_nemo import process_ocean
from ppfix.process_nemo import process_sice
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description='Post-process coupled UM, NEMO, and SI3 model output.'
    )
    parser.add_argument('input_directory', type=Path)
    parser.add_argument('output_directory', type=Path)
    parser.add_argument('metadata_file', type=Path)
    parser.add_argument(
        '--replace', action='store_true', help='Replace existing ocean and sea-ice output files.'
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if not args.metadata_file.is_file():
        raise FileNotFoundError(f'Metadata file {args.metadata_file} does not exist.')

    metadata = configparser.ConfigParser(interpolation=None)
    metadata.read(args.metadata_file)

    process_atmos(args.input_directory, args.output_directory / 'atmos', metadata, 'model_atmos')
    process_ocean(args.input_directory, args.output_directory / 'nemo', metadata, args.replace)
    process_sice(args.input_directory, args.output_directory / 'sice', metadata, args.replace)


if __name__ == '__main__':
    main()




