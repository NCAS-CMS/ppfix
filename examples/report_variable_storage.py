import argparse
from pathlib import Path

import h5py


def read_file_signature(input_file: Path) -> str:
    with input_file.open('rb') as handle:
        signature = handle.read(8)
    return signature.hex()


def parse_args():
    parser = argparse.ArgumentParser(
        description='Report per-variable on-disk storage size for a NetCDF4/HDF5 file.'
    )
    parser.add_argument('input_file', type=Path)
    return parser.parse_args()


def format_gib(num_bytes: int) -> float:
    return num_bytes / (1024 ** 3)


def report_variable_storage(input_file: Path) -> None:
    input_file = input_file.expanduser().resolve()
    if not input_file.is_file():
        raise FileNotFoundError(f'Input file {input_file} does not exist.')

    rows = []
    try:
        handle = h5py.File(input_file, 'r')
    except OSError as exc:
        signature_hex = read_file_signature(input_file)
        raise OSError(
            f'Unable to open {input_file} with h5py ({exc}). '\
            f'File signature bytes: {signature_hex}'
        ) from exc

    with handle:
        def visitor(name, obj):
            if not isinstance(obj, h5py.Dataset):
                return

            logical_bytes = int(obj.size * obj.dtype.itemsize)
            storage_bytes = int(obj.id.get_storage_size())
            ratio = None
            if logical_bytes > 0:
                ratio = storage_bytes / logical_bytes

            rows.append(
                {
                    'name': name,
                    'shape': str(obj.shape),
                    'dtype': str(obj.dtype),
                    'logical_bytes': logical_bytes,
                    'storage_bytes': storage_bytes,
                    'ratio': ratio,
                }
            )

        handle.visititems(visitor)

    rows.sort(key=lambda row: row['storage_bytes'], reverse=True)

    print(f'File: {input_file}')
    print(
        'name,shape,dtype,logical_bytes,storage_bytes,logical_gib,storage_gib,storage_to_logical_ratio'
    )
    for row in rows:
        ratio_text = '' if row['ratio'] is None else f"{row['ratio']:.4f}"
        print(
            f"{row['name']},{row['shape']},{row['dtype']},"
            f"{row['logical_bytes']},{row['storage_bytes']},"
            f"{format_gib(row['logical_bytes']):.4f},{format_gib(row['storage_bytes']):.4f},"
            f"{ratio_text}"
        )


def main():
    args = parse_args()
    report_variable_storage(args.input_file)


if __name__ == '__main__':
    main()