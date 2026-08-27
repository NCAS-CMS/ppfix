import cf
from ppfix.utils import meta2attr, build_simulation_name, make_output_file_name
from ppfix.inventory import inspect_field
from pathlib import Path
from uuid import uuid4
from tables.cmip_identifiers import CMIPIdentifiers
from ppfix.chunking import get_umchunking
import time


def write_field(
    field: cf.Field,
    simulation: str,
    extra_properties: dict[str, object],
    output_target_dir: str,
    chunk_shape: tuple[int, ...] | None = None,
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

    print(field)
    print(f'Writing field [{field.identity()}] to {output_path} with chunk shape {chunk_shape}')
    t1 = time.perf_counter()
    cf.write(field, 
             dataset_name=str(output_path), 
             fmt="NETCDF4",
             single=True,
             dataset_chunks='4 MiB')
    t2 = time.perf_counter() - t1

    print(f'Written {output_path} in {t2:.2f}s')



def process_atmos(input_folder, output_folder, metadata, component):
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


    for f in input_folder.glob('*'):
        # skip existing nemo or sice files or any hidden files
        if f.suffix == '.nc' or not f.is_file() or f.name.startswith('.'):
            continue

        print(f'Processing {f} ({input_folder})')
        fields = cf.read(str(f))

        # simulation name is constructed from the project, the experiment, and the runid 
        simulation = build_simulation_name(metadata)

        cmip = CMIPIdentifiers()

        t1 = time.perf_counter()
        for field in fields:
            meta2attr(metadata, field, component)

            extra_properties = inspect_field(cmip, field)
            extra_properties['tracking_id'] = str(uuid4())

            # Determine chunk shape based on the field's shape
            chunk_shape = get_umchunking(field)
            write_field(field, simulation, extra_properties, output_folder, chunk_shape)
            #exit()  # Exit after processing the first field for testing purposes
        t2 = time.perf_counter() - t1
        print(f'Processed {f} in {t2:.2f}s')
