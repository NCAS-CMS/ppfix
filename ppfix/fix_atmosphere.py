import cf
from ppfix.utils import meta2attr, build_simulation_name, make_output_file_name, meta2output
from ppfix.inventory import inspect_field
from pathlib import Path
from typing import Any
from uuid import uuid4
from tables.cmip_identifiers import CMIPIdentifiers
from ppfix.chunking import get_umchunking
import time


DEFAULT_WRITE_KWARGS = {
    'fmt': 'NETCDF4',
    'single': True,
    'dataset_chunks': '4 MiB',
}


def _format_gib(num_bytes: int) -> float:
    return num_bytes / (1024 ** 3)


def _estimate_field_payload_gib(field: cf.Field) -> float | None:
    shape = getattr(field, 'shape', None)
    dtype = getattr(field, 'dtype', None)
    if shape is None or dtype is None:
        return None

    itemsize = getattr(dtype, 'itemsize', None)
    if itemsize is None:
        return None

    elements = 1
    for extent in shape:
        elements *= extent
    return elements * itemsize / (1024 ** 3)


def write_field(
    field: cf.Field,
    simulation: str,
    extra_properties: dict[str, object],
    output_target_dir: str,
    chunk_shape: tuple[int, ...] | None = None,
    field_index: int = 0,
    total_fields: int = 1,
    write_kwargs: dict[str, Any] | None = None,
    report_timings: bool = False,
) -> None:
    """
    Write a field to a NetCDF file with the specified properties.

    Parameters
    ----------
    field:
        A single cf.Field object to be written.
    simulation:
        The name of the simulation (experiment) for naming the output file.
    extra_properties:
        A dictionary containing new properties for the field, including
        'cms_table', 'temporal_cell_method', 'identity', and 'cmip6_variable'.
    chunk_shape:
        Optional tuple specifying the chunk shape for the NetCDF file. If None,
        default chunking will be used (size = 4MB)
    output_target_dir:
        The directory where the output NetCDF file will be saved.
    """

    # Construct the output file name
    filename = make_output_file_name(simulation, extra_properties)
    output_path = Path(output_target_dir) / filename

    # Ensure the output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write the field to the NetCDF file
    # using default compression 
    # the dataset chunks will be used for coordinate variables 
    # even if the chunk_shape is specified, but the data variable
    # will respect the specificied chunk_shape if provided.

    for k, v in extra_properties.items():
        if v is not None:
            field.set_property(k, v)

    if chunk_shape is not None:
        field.nc_set_dataset_chunksizes(chunk_shape)

    payload_gib = _estimate_field_payload_gib(field)
    if payload_gib is None:
        payload_summary = 'unknown raw payload'
    else:
        payload_summary = f'~{payload_gib:.2f} GiB raw payload'

    print(field)
    print(
        f'Writing field [{field.identity()}] ({field_index+1}/{total_fields}) '
        f'to {output_path} with chunk shape {chunk_shape} ({payload_summary})'
    )
    t1 = time.perf_counter()
    effective_write_kwargs = dict(DEFAULT_WRITE_KWARGS)
    if write_kwargs is not None:
        effective_write_kwargs.update(write_kwargs)
    cf.write(field, dataset_name=str(output_path), **effective_write_kwargs)
    t2 = time.perf_counter() - t1

    output_size = None
    if output_path.exists():
        output_size = output_path.stat().st_size

    if output_size is None:
        print(f'Written {output_path} in {t2:.2f}s')
    else:
        print(
            f'Written {output_path} in {t2:.2f}s '
            f'(size {output_size} bytes, {_format_gib(output_size):.2f} GiB)'
        )

    if report_timings:
        if output_size is None:
            print(f'   write time: {t2:.2f}s with write options {effective_write_kwargs}')
        else:
            print(
                f'   write time: {t2:.2f}s with write options {effective_write_kwargs}; '
                f'output size: {output_size} bytes ({_format_gib(output_size):.2f} GiB)'
            )



def process_atmos(
    input_folder,
    output_folder,
    metadata,
    component,
    report_timings: bool = False,
):
    """
    Process all files in folder which are _not_ netcdf files and 
    use fix_atmosphere to write them as netcdf files in the output folder.
  
    Parameters
    ----------
    input_folder:
        The directory containing the input NetCDF files.
    output_folder:
        The directory where the processed NetCDF files will be saved.
    metadata:
        A dictionary containing metadata information for the fields.        
    component:
        The component section to use from metadata.conf, such as model_atmos,
        model_ocean, or model_seaice.
    """

    input_folder = Path(input_folder)
    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    write_kwargs = meta2output(metadata)

    for f in input_folder.glob('*'):
        # skip existing nemo or sice files or any hidden files
        if f.suffix == '.nc' or not f.is_file() or f.name.startswith('.'):
            continue

        print(f'Processing {f} ({input_folder})')
        read_started = time.perf_counter()
        fields = cf.read(str(f))
        read_elapsed = time.perf_counter() - read_started
        if report_timings:
            print(f'Open/read setup for {f.name} completed in {read_elapsed:.2f}s')

        # simulation name is constructed from the project, the experiment, and the runid 
        simulation = build_simulation_name(metadata)

        cmip = CMIPIdentifiers()

        t1 = time.perf_counter()
        for i, field in enumerate(fields):
            field_started = time.perf_counter()
            meta2attr(metadata, field, component)

            prep_started = time.perf_counter()
            extra_properties = inspect_field(cmip, field)
            extra_properties['tracking_id'] = str(uuid4())

            # Determine chunk shape based on the field's shape
            chunk_shape = get_umchunking(field)
            prep_elapsed = time.perf_counter() - prep_started
            write_field(
                field,
                simulation,
                extra_properties,
                output_folder,
                chunk_shape,
                i,
                len(fields),
                write_kwargs=write_kwargs,
                report_timings=report_timings,
            )
            if report_timings:
                total_field_elapsed = time.perf_counter() - field_started
                print(
                    f'   field prep time: {prep_elapsed:.2f}s; '
                    f'total field pipeline time: {total_field_elapsed:.2f}s'
                )
            #exit()  # Exit after processing the first field for testing purposes
        t2 = time.perf_counter() - t1
        print(f'Processed {f} in {t2:.2f}s')
        if report_timings:
            print(f'Total wall time for {f.name}: {read_elapsed + t2:.2f}s')
