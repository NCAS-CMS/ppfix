import argparse
import configparser
from contextlib import contextmanager
from pathlib import Path
import tempfile

from ppfix.fix_atmosphere import process_atmos
from ppfix.process_nemo import process_ocean
from ppfix.process_nemo import process_sice


def parse_args():
    parser = argparse.ArgumentParser(
        description='Post-process one input file from a large coupled UM, NEMO, or SI3 run.'
    )
    parser.add_argument('input_file', type=Path)
    parser.add_argument('output_directory', type=Path)
    parser.add_argument('metadata_file', type=Path)
    return parser.parse_args()


def load_metadata(metadata_file: Path) -> configparser.ConfigParser:
    if not metadata_file.is_file():
        raise FileNotFoundError(f'Metadata file {metadata_file} does not exist.')

    metadata = configparser.ConfigParser(interpolation=None)
    metadata.read(metadata_file)
    return metadata


def infer_component(input_file: Path) -> str:
    if input_file.name.startswith('nemo') and input_file.suffix == '.nc':
        return 'nemo'
    if input_file.name.startswith('si3') and input_file.suffix == '.nc':
        return 'sice'
    return 'atmos'


@contextmanager
def staged_input_directory(input_file: Path):
    with tempfile.TemporaryDirectory(prefix='ppfix-') as tempdir:
        staged_dir = Path(tempdir)
        staged_file = staged_dir / input_file.name
        staged_file.symlink_to(input_file.resolve())
        yield staged_dir


def process_single_file(input_file: Path, output_directory: Path, metadata) -> None:
    component = infer_component(input_file)

    with staged_input_directory(input_file) as staged_dir:
        if component == 'nemo':
            process_ocean(staged_dir, output_directory / 'nemo', metadata, True)
        elif component == 'sice':
            process_sice(staged_dir, output_directory / 'sice', metadata, True)
        else:
            process_atmos(staged_dir, output_directory / 'atmos', metadata, 'model_atmos')


def main():
    args = parse_args()
    metadata = load_metadata(args.metadata_file)
    process_single_file(args.input_file, args.output_directory, metadata)


if __name__ == '__main__':
    main()