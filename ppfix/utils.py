def _clean_metadata_value(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value

def meta2output(metadata):
    """ 
    Generate a dictionary of write options from the metadata.conf file.
    """
    write_kwargs = {}
    if 'output' in metadata.sections():
        print(f'Using output section from metadata for write options: {metadata["output"]}')
        expected = ['compress', 'single', 'dataset_chunks']
        for key, value in metadata['output'].items():
            if key not in expected:
                print(f'Warning: unexpected key "{key}" in output section of metadata; ignoring it.')
        if 'compress' in metadata['output']:
            write_kwargs['compress'] = metadata.getint('output', 'compress')
        if 'single' in metadata['output']:
            write_kwargs['single'] = metadata.getboolean('output', 'single')
        if 'dataset_chunks' in metadata['output']:
            write_kwargs['dataset_chunks'] = metadata.get('output', 'dataset_chunks')
    return write_kwargs

def meta2attr(metadata, field, component):

    """Copy metadata sections onto a cf.Field as field properties.

    Parameters
    ----------
    metadata:
        A configparser.ConfigParser instance created from metadata.conf.
    field:
        A cf.Field object that will receive the properties.
    component:
        The model component section to copy, for example model_atmos,
        model_ocean, or model_seaice. The bare names atmos/ocean/seaice
        are also accepted.
    """

    if component in metadata:
        component_section = component
    else:
        component_section = f'model_{component}'

    sections = ['General', 'run_specific', 'model_general']
    if component_section in metadata:
        sections.append(component_section)

    for section in sections:
        for key, value in metadata[section].items():
            field.set_property(key, _clean_metadata_value(value))

    if 'run_specific.variant_id' in metadata:
        runid = field.get_property('runid', None)
        if runid is not None:
            variant_map = metadata['run_specific.variant_id']
            if runid in variant_map:
                field.set_property('variant_id', variant_map[runid])


def build_simulation_name(metadata):
    """ 
    Create simulation name from metadata.conf information
    """
    project = metadata['General'].get('activity-id', 'unknown')
    experiment = metadata['General'].get('experiment', 'unknown')
    runid = metadata['run_specific'].get('runid', 'unknown')
    return f'{project}_{experiment}_{runid}'

def make_output_file_name(simulation, properties):
    """
    Returns the constructed output filename.
    """
    if properties['zonal_cell_method'] in ['Mean','mean']:
        filename = f"{simulation}__{properties['cms_table']}zm__{properties['start_date']}__{properties['temporal_cell_method']}__{properties['identity']}__{properties['cmip6_variable']}.nc"
    else:
        filename = f"{simulation}__{properties['cms_table']}__{properties['start_date']}__{properties['temporal_cell_method']}__{properties['identity']}__{properties['cmip6_variable']}.nc"
    filename = filename.lower()
    return filename