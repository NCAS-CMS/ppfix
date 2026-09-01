import argparse
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description='Generate a manifest of input files for Slurm array processing.'
    )
    parser.add_argument('input_directory', type=Path)
    parser.add_argument('output_manifest', type=Path)
    parser.add_argument(
        '--pattern',
        action='append',
        dest='patterns',
        help='Glob pattern to include. May be repeated. Defaults to all non-hidden files.',
    )
    return parser.parse_args()


def iter_input_files(input_directory: Path, patterns: list[str] | None):
    if patterns:
        for pattern in patterns:
            yield from input_directory.glob(pattern)
    else:
        yield from input_directory.glob('*')


def main():
    args = parse_args()

    input_directory = args.input_directory.expanduser().resolve()
    if not input_directory.is_dir():
        raise NotADirectoryError(f'Input directory {input_directory} does not exist.')

    output_manifest = args.output_manifest.expanduser().resolve()
    output_manifest.parent.mkdir(parents=True, exist_ok=True)

    files = []
    for file_path in iter_input_files(input_directory, args.patterns):
        if not file_path.is_file() or file_path.name.startswith('.'):
            continue
        files.append(str(file_path.resolve()))

    files = sorted(dict.fromkeys(files))
    output_manifest.write_text('\n'.join(files) + ('\n' if files else ''))


if __name__ == '__main__':
    main()