import configparser
from contextlib import contextmanager
from pathlib import Path
import tempfile

from ppfix.fix_atmosphere import process_atmos


TEST_INPUT_FILE = Path('/Volumes/Lawrence4TB/u-dz876/dz876a.p81950jan')
META_FILE = Path(__file__).parent.parent / 'experiment_configs/n1280o12.conf'
TEMP_ROOT = Path('/Volumes/Lawrence4TB/ppfix_tmp')



def load_metadata(metadata_file: Path) -> configparser.ConfigParser:
    metadata_file = metadata_file.expanduser().resolve()
    if not metadata_file.is_file():
        raise FileNotFoundError(f'Metadata file {metadata_file} does not exist.')

    metadata = configparser.ConfigParser(interpolation=None)
    metadata.read(metadata_file)
    return metadata


def ensure_temp_root(temp_root: Path) -> Path:
    temp_root = temp_root.expanduser().resolve()
    temp_root.mkdir(parents=True, exist_ok=True)
    return temp_root


def format_gib(num_bytes: int) -> float:
    return num_bytes / (1024 ** 3)


@contextmanager
def staged_input_directory(input_file: Path):
    input_file = input_file.expanduser().resolve()
    if not input_file.is_file():
        raise FileNotFoundError(f'Input file {input_file} does not exist.')

    temp_root = ensure_temp_root(TEMP_ROOT)
    with tempfile.TemporaryDirectory(prefix='ppfix-probe-input-', dir=temp_root) as tempdir:
        staged_dir = Path(tempdir)
        staged_file = staged_dir / input_file.name
        staged_file.symlink_to(input_file)
        yield staged_dir


@contextmanager
def temporary_output_directory():
    temp_root = ensure_temp_root(TEMP_ROOT)
    with tempfile.TemporaryDirectory(prefix='ppfix-probe-output-', dir=temp_root) as tempdir:
        yield Path(tempdir)


def main():
    with staged_input_directory(TEST_INPUT_FILE) as input_dir, temporary_output_directory() as output_dir:
        print(f'Using hardwired input file: {TEST_INPUT_FILE}')
        print(f'Using temporary root: {TEMP_ROOT.expanduser().resolve()}')
        print(f'Using staged input directory: {input_dir}')
        print(f'Using output directory: {output_dir}')

        metadata = load_metadata(META_FILE)
        # change this for probing different output options; these are good defaults for most cases
        metadata['output']['compress'] = '1'

        process_atmos(
            input_dir,
            output_dir,
            metadata,
            'model_atmos',
            report_timings=True,
        )

        output_files = sorted(output_dir.glob('*.nc'))
        if not output_files:
            print('No NetCDF outputs were found for size reporting.')
            return

        print(f'Generated {len(output_files)} NetCDF file(s); reporting output file sizes:')
        for output_file in output_files:
            size_bytes = output_file.stat().st_size
            print(f'  {output_file.name}: {size_bytes} bytes ({format_gib(size_bytes):.3f} GiB)')


if __name__ == '__main__':
    main()