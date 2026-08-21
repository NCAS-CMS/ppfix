from pathlib import Path
import re
from tables.cmip_identifiers import CMIPIdentifiers
from ppfix.time_inspection import infer_temporal_frequency
from ppfix.chunking import get_umchunking
from ppfix.utils import make_output_file_name
import cf

DEMARK = '\n------------------------------------------------------------\n'




def inspect_field(cmip, fld, logfile=None):
    """ 
    Inspect a cf.Field and return some additional properties which can be used to construct a filename 
    (and be added to the field properties if desired). 
    """

    t, v = cmip.find(fld)
    myt, start_date = infer_temporal_frequency(fld)
    tcm = _format_temporal_cell_method(fld)
    xcm = _format_temporal_cell_method(fld, choice='X')

    identity = fld.get_property('standard_name', None)
    if identity is None:
        identity = fld.get_property('long_name', None)
    if identity is None:
        identity = fld.get_property('um_stash_source','unknown')
    else:
        identity =  re.sub(r'[^0-9A-Za-z]+', '_', identity).strip('_')

    if v in [None, 'unknown', 'expression']:
        v = ''

    new_properties = {
        'cmip6_table': t,
        'cmip6_variable': v,
        'cms_table': myt,
        'temporal_cell_method': tcm,
        'zonal_cell_method': xcm,
        'identity': identity,
        'start_date': start_date, 
    }

    if logfile is not None:
        logfile.write(f'   CMIP6 table: {t}; CMS table: {myt};  Temporal cell method: {tcm}; Zonal cell method: {xcm}; identity: {identity}; variable: {v}\n')
    return new_properties
    

def _format_temporal_cell_method(field, choice='T'):
    """Return the cell method applied on the temporal axis, e.g. 'mean'."""
    t_axis_key = field.domain_axis(choice, key=True, default=None)
    if t_axis_key is None:
        return None

    for cell_method in field.cell_methods():
        if isinstance(cell_method, str):
            cell_method = field.construct(cell_method)

        axis_keys = cell_method.get_axes(()) if hasattr(cell_method, 'get_axes') else ()
        if t_axis_key not in axis_keys:
            continue

        if hasattr(cell_method, 'get_method'):
            method = cell_method.get_method(default=None)
            if method:
                return method

        cm_text = str(cell_method)
        if ':' in cm_text:
            return cm_text.split(':', 1)[1].strip().split()[0]
        return cm_text

    return None


def _format_cell_methods(field):
    """
    Return cell methods as ['T:mean', ...] style strings.
    """
    axis_short_by_key = {}
    for short_axis in ('T', 'Z', 'Y', 'X'):
        axis_key = field.domain_axis(short_axis, key=True, default=None)
        if axis_key is not None:
            axis_short_by_key[axis_key] = short_axis

    formatted = []
    for cell_method in field.cell_methods():
        if isinstance(cell_method, str):
            cell_method = field.construct(cell_method)

        method = None
        if hasattr(cell_method, 'get_method'):
            method = cell_method.get_method(default=None)

        if not method:
            cm_text = str(cell_method)
            if ':' in cm_text:
                method = cm_text.split(':', 1)[1].strip().split()[0]
            else:
                method = cm_text

        axis_keys = ()
        if hasattr(cell_method, 'get_axes'):
            axis_keys = cell_method.get_axes(())

        axis_short = ''.join(axis_short_by_key.get(k, '?') for k in axis_keys) if axis_keys else '?'
        formatted.append(f'{axis_short}:{method}')

    return formatted



def inventory(experiment, target_dir, inv_file=None):
    """ 
    Return a full inventory of all the files in the target directory.
    """
    target_dir = Path(target_dir).expanduser()
    target_dir.mkdir(parents=True, exist_ok=True)
    if inv_file is None:
        inv_file = target_dir / 'inventory.txt'

    cmip = CMIPIdentifiers()

    with open(inv_file, 'w') as inv_file:
        for f in target_dir.glob('d*'):
            if f.is_file():
                try:
                    flds = cf.read(str(f))
                    inv_file.write(f'{DEMARK}Inventory for {f}. (cf={cf.__version__})\n')
                    simulation = f'{experiment}_{flds[0].get_property("runid", "XXXX")}'
                    for f in flds:
                        inv_file.write(f'{f.__repr__()}\n')
                        inspected = inspect_field(cmip, f, logfile=inv_file)
                        cs = f.nc_dataset_chunksizes()
                        cm = _format_cell_methods(f)
                        inv_file.write(f'   Cell methods: {cm}; Current Chunking: {cs}; Possible Chunking: {get_umchunking(f)}\n')
                        inv_file.write(f'   Output file?: {make_output_file_name(simulation, inspected)}\n')
                        print(f'   Output file: {make_output_file_name(simulation, inspected)}\n')

                except Exception as e:
                    print(f'{DEMARK}Error reading {f} with cf: {e}{DEMARK}')
                    raise

            else:
                inv_file.write(f'{DEMARK}Found unexpected directory {f}, skipping.{DEMARK}')
        


if __name__ == '__main__':
    import sys
    target_dir = sys.argv[1] if len(sys.argv) > 1 else None
    if target_dir is None:
        print('Usage: python inventory.py <target_dir>')
        sys.exit(1)
    print(f'Creating inventory for {target_dir} with cf version {cf.__version__}')
    experiment = 'n1280o12_control'
    inventory(experiment, target_dir)