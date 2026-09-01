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


def resolve_input_roots(input_directory: Path) -> list[Path]:
    if input_directory.is_dir():
        return [input_directory]

    parent = input_directory.parent
    if not parent.is_dir():
        raise NotADirectoryError(f'Input directory {input_directory} does not exist.')

    matches = sorted(path for path in parent.glob(f'{input_directory.name}*') if path.is_dir())
    if not matches:
        raise NotADirectoryError(f'Input directory {input_directory} does not exist and no matching directories were found.')

    return matches


def iter_input_files(input_roots: list[Path], patterns: list[str] | None):
    for input_root in input_roots:
        if patterns:
            for pattern in patterns:
                yield from input_root.glob(pattern)
        else:
            yield from input_root.glob('*')


def main():
    args = parse_args()

    input_directory = args.input_directory.expanduser().resolve()
    input_roots = resolve_input_roots(input_directory)

    output_manifest = args.output_manifest.expanduser().resolve()
    output_manifest.parent.mkdir(parents=True, exist_ok=True)

    files = []
    for file_path in iter_input_files(input_roots, args.patterns):
        if not file_path.is_file() or file_path.name.startswith('.'):
            continue
        files.append(str(file_path.resolve()))

    files = sorted(dict.fromkeys(files))
    output_manifest.write_text('\n'.join(files) + ('\n' if files else ''))


if __name__ == '__main__':
    main()