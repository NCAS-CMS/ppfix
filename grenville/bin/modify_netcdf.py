#!/usr/bin/env python
"""
Python script modifies metadata for netCDF files written by XIOS.
There are 3 possible modifications
1) Add Global metadata from rose suite file rose-suite.info
2) Fix grid metadata for data on rotated pole grids to be cf compliant
3) Fix cell_methods metadata and time/time bounds data for monthly means of daily output at different time offset values

add cell_measures to cice fields
add standard names to cice fields
update cell_methods for cice fields
"""

import sys
import os
import time
import re
import fnmatch
import netCDF4
from cf import Units
import configparser
import uuid
import csv
from heights import fix_heights
from ice import fix_ice_indices
from ocean import fix_ocean_indices
from zmean import fix_zmeans

# File patterns
cice_pattern = re.compile(r'[a-z]{2}[0-9]{3}[i][_][0-9]')
nemo_pattern = re.compile(r'[a-z]{2}[0-9]{3}[o][_][0-9]')
atmos_hybrid_height_pattern = re.compile(r'mon_[uvt]_') # atmos uvt grids
atmos_hybrid_height_pattern_2 = None # uv zonal files
atmos_hybrid_height_pattern_3 = None # hrs files
cordex_pattern = re.compile(r'_[uvt]_pt_cordex')
zonal_pattern = re.compile(r'_z_')

printFlush=True

def expandvars (var):
    """expand all environment variables in var, recursively"""

    var1 = var
    index = 0
    maxindex = 100
    while True:
        var2 = os.path.expandvars(var1)
        if var1 == var2:
            break
        if index > maxindex:
            print ('WARNING possible infinite recursion expanding variable value',var2,flush=printFlush)
            break
        var1 = var2
        index += 1

    return var1

def convert_units(time,units):

    # Split time into value and unit
    m = re.match(r'(\d+(?:\.\d*)?|\.\d+) *(\w+)',time)
    time_value= float(m.group(1))
    time_units= m.group(2)

    # XIOS writes udunits compatible unit strings
    # ('yr','month','d','h','min','s')
    time_new = Units.conform(time_value,Units(time_units),Units(units))

    return time_new

def add_suite_info(nc,file_date):

    # Get location of rose-suite.info file either from environment
    # or the second argument.
    if 'ROSE_SUITE_DIR' in os.environ:
        suite_info_file = os.path.join(os.environ['ROSE_SUITE_DIR'],
                                       'rose-suite.info')
    else:
        if len(sys.argv) ==2 and os.path.exists(sys.argv[1]):
            suite_info_file = sys.argv[1]
        else:
            print ('Please supply location of rose-suite.info file '
                   'as an argument if not running this script from the suite',flush=printFlush)
            sys.exit(1)

    print ("suite_info_file =",suite_info_file,flush=printFlush)
    config = configparser.ConfigParser()
    with open(suite_info_file) as fp:
        config.read_string("[top]\n" + fp.read())
    suite_info = config['top']

    for key in suite_info:
        #print ("key,val = ",key,suite_info[key],flush=printFlush)
        nc.setncattr(key,suite_info[key])

    try:
        # If creation_time global attribute exists keep it
        creation_time = nc.getncattr('creation_time')
        print ("creation_time =",creation_time ,flush=printFlush)
    except (AttributeError):
        # If creation_time global attribute doen't exist use file date
        print ("file_date =",file_date,flush=printFlush)
        nc.setncattr('creation_time',file_date)

def fix_grid_metadata(nc):

    north_pole = None
    # Check if rotated grid
    for var in nc.variables:
        v = nc.variables[var]
        try:
            if v.getncattr('grid_mapping_name') == 'rotated_latitude_longitude':
                north_pole_lon = v.getncattr('grid_north_pole_longitude')
                north_pole_lat = v.getncattr('grid_north_pole_latitude')
                north_pole = (north_pole_lon,north_pole_lat)
                print ('North pole of rotated grid =',north_pole,flush=printFlush)
                break
        except AttributeError:
            pass

    if (north_pole is not None):
        # Loop over dimensions
        for dim in nc.dimensions:
            try:
                v = nc.variables[dim]
                standard_name = v.getncattr('standard_name')
            except (KeyError, AttributeError):
                continue

            if (standard_name == 'longitude' or standard_name == 'latitude'):
                print('--- ',dim,flush=printFlush)
                new_standard_name = 'grid_'+standard_name
                print('    ',standard_name,new_standard_name,flush=printFlush)
                # Fix standard_name for rotated pole grid

                try:
                    long_name = v.getncattr('long_name')
                except (AttributeError):
                    pass
                else:
                    new_long_name = long_name+' in rotated pole grid'
                    print('    ',long_name,new_long_name,flush=printFlush)
                    # Fix long_name for rotated pole grid
                    v.setncattr('long_name', new_long_name)

                try:
                    units = v.getncattr('units')
                except (AttributeError):
                    pass
                else:
                    new_units = 'degrees'
                    print('    ',units,new_units,flush=printFlush)
                    # Fix units for rotated pole grid
                    v.setncattr('units', new_units)
    else:
        print('Netcdf file has no rotated pole defined',flush=printFlush)

def fix_time_offset_metadata(nc):

    time_coord = 'time_centered'
    try:
        time = nc.variables[time_coord]
    except KeyError:
        print ('time coordinate {} does not exist exiting'.format(time_coord),flush=printFlush)
        return
    else:
        print ("time =",time[:],flush=printFlush)

    try:
        calendar = time.getncattr('calendar')
    except (AttributeError):
        print ('time coordinate does not have calendar attribute exiting',flush=printFlush)
        return
    else:
        print ("calendar =",calendar,flush=printFlush)
        if calendar != "360_day":
            print ('Calendar is not 360 day exiting',flush=printFlush)
            return

    try:
        units = time.getncattr('units')
    except (AttributeError):
        print ('time coordinate does not have units attribute exiting',flush=printFlush)
        return
    else:
        print ("units =",units,flush=printFlush)
        units_since_reftime = units.split()[0]
        print ("units_since_reftime =",units_since_reftime,flush=printFlush)
        if not Units(units_since_reftime).equivalent(Units("s")):
            print ('Time unit is not convertible into seconds exiting',flush=printFlush)
            return

    try:
        time_coord_bounds = time.getncattr('bounds')
    except (AttributeError):
        time_coord_bounds = None
    else:
        #print ("time_coord_bounds =",time_coord_bounds,flush=printFlush)
        time_bounds = nc.variables[time_coord_bounds]
        #print ("time_bounds =",time_bounds[:],flush=printFlush)
        period = time_bounds[0,1] - time_bounds[0,0]
        print ("period = ",period,flush=printFlush)
        period_sec = Units.conform(period,Units(units_since_reftime),Units("s"))
        print ("period_sec = ",period_sec,flush=printFlush)

    offset0 = None
    modified = 0
    for var in nc.variables:
        v = nc.variables[var]

        try:
            online_operation = v.getncattr('online_operation')
            interval_operation = v.getncattr('interval_operation')
        except (AttributeError):
            continue

        # Only modify metadata if field is a 30 day mean sampled every 24 hours
        if online_operation != 'average' or \
           period_sec != 2592000.0 or \
           convert_units(interval_operation,"s") != 86400.0:
            continue

        try:
            interval_offset = v.getncattr('interval_offset')
        except (AttributeError):
            offset = 0
        else:
            offset = convert_units(interval_offset,units_since_reftime)
        print(var,": offset =",offset,flush=printFlush)

        # Assume file only has one offset value and applies to all fields
        if offset0 is not None and offset != offset0:
            print ('File has more than one offset value (',offset0,offset,') exiting',flush=printFlush)
            return

        offset0 = offset
        modified += 1
        # Change cell methods
        #cell_methods = v.getncattr('cell_methods')
        #print ('cell_methods =',cell_methods,flush=printFlush)
        v.setncattr('cell_methods','time: point within days time: mean over days')

    print ('modified =',modified,flush=printFlush)
    if modified > 0:
        # Modify time coordinate with offset value
        time[:] = time[:] + offset
        print ("time =",time[:],flush=printFlush)

        # Modify time coordinate bounds with offset value
        if time_coord_bounds is not None:
            time_bounds[:,0] = time_bounds[:,0] + offset
            time_bounds[:,1] = time_bounds[:,1] + offset - Units.conform(1.0,Units('d'),Units(units_since_reftime))
        print ("time_bounds =",time_bounds[:],flush=printFlush)

def add_model_metadata(config,meta_sections,ncfile,nc):

    for section in meta_sections:
        #print ("section =",section)
        metadata = config[section]
        try:
            match = metadata['filename_match'][1:-1] # Strip leading and trailing quotes
        except KeyError:
            print (f"{section} doesn't have filename_match set, skipping")
            continue

        match = expandvars(match)
        #print ("match =",match)
        if fnmatch.fnmatch(ncfile,match):
            #print (ncfile,'matches')
            for attr in metadata:
                if attr == 'filename_match': continue
                #print (attr,'=',metadata[attr])
                #Dan Edits ----
                attrval=metadata[attr]

                # is attrval a string of digits? "7500" or "7500." or "7500.0"?
                if attrval.replace('.','').isdigit():
                    #Yes - so make this a float
                    attrval = float(attrval)
     
                #check this is a string bounded by single quotes
                elif len(attrval)>1:
                    if (attrval[0]=="'" and attrval[-1]=="'") or (attrval[0]=='"' and attrval[-1]=='"'):
                        attrval = attrval[1:-1] # Strip leading and trailing quotes
                        attrval = expandattr(attrval)
                #------------------------
                # Write global attribute
                nc.setncattr(attr,attrval)

                if attr == 'initialization_index':
                    initialization_index = expandattr(metadata[attr][1:-1])
                if attr == 'realization_index':
                    realization_index = expandattr(metadata[attr][1:-1])
                if attr == 'physics_index':
                    physics_index = expandattr(metadata[attr][1:-1])
                if attr == 'forcing_index':
                    forcing_index = expandattr(metadata[attr][1:-1])

            variant_id = 'r' + realization_index + 'i' + initialization_index + 'p' + physics_index + 'f' + forcing_index
            nc.setncattr('variant_id', variant_id)

            nc.setncattr('Conventions', 'CF-1.10')

        #else:
            #print (ncfile,'does not match')


def expandattr(attrval):

    if attrval.find('%uuid%') >= 0:
        attrval = attrval.replace('%uuid%', str(uuid.uuid4()))
    else:
        attrval = expandvars (attrval)

    return attrval

def main():

    with open('cice_vars.csv', mode='r') as infile:
         reader = csv.reader(infile)
         cice_map = {rows[0]:[rows[1],rows[2]] for rows in reader}
    infile.close()

    with open('nemo_vars.csv', mode='r') as infile:
         reader = csv.reader(infile)
         nemo_map = {rows[0]:rows[1] for rows in reader}
    infile.close()

    # Read rose-app-run.conf
    config = configparser.ConfigParser(interpolation=None)
    config.read('rose-app-run.conf')
    app_opt = config['mod_netcdf']

    meta_section='model_metadata'
    mlen = len(meta_section)
    meta_sections = []
    for sec in config.sections():
        if sec[0:mlen] == meta_section:
            model = sec[mlen+1:-1]
            section = f"{meta_section}({model})"
            meta_sections.append(section)

    netcdf_dir = expandvars(app_opt['netcdf_dir']).strip('\'')
    print ('netcdf_dir = ',netcdf_dir,flush=printFlush)
    try:
        os.chdir(netcdf_dir)
    except:
        sys.exit('Error changing to directory '+netcdf_dir)

    ncfiles = (f for f in os.listdir('.') if os.path.splitext(f)[1] == '.nc')
    for  ncfile in ncfiles:

        mtime = os.path.getmtime(ncfile)
        file_date = time.strftime('%Y-%m-%d %H:%M',time.localtime(mtime))
        print ('file_date =',file_date,flush=printFlush)

        t0 = time.perf_counter()
        nc = netCDF4.Dataset(ncfile,'a')
        print ('NetCDF file',ncfile,'opened',flush=printFlush)

        if app_opt['add_global_metadata'] == 'true':
           t00 = time.perf_counter()
           # Add rose-suite.info metadata to netcdf file as global attributes
           add_suite_info(nc, file_date)
           t01 = time.perf_counter()
           print ('Time to add global metadata to file',ncfile,' is',t01-t00,' seconds',flush=printFlush)

        if app_opt['fix_grid_metadata'] == 'true':
           t00 = time.perf_counter()
           # Fix lat/lon metadata for rotated grid LAM runs
           fix_grid_metadata(nc)
           t01 = time.perf_counter()
           print ('Time to fix grid metadata in file',ncfile,' is',t01-t00,' seconds',flush=printFlush)

        if app_opt['mod_cell_methods'] == 'true':
           t00 = time.perf_counter()
           # Fix time metadata for monthly means sampled every 24 hours at offset hours
           fix_time_offset_metadata(nc)
           t01 = time.perf_counter()
           print ('Time to modify cell_methods for file',ncfile,' is',t01-t00,' seconds',flush=printFlush)

        t00 = time.perf_counter()
        add_model_metadata(config,meta_sections,ncfile,nc)
        t01 = time.perf_counter()
        print ('Time to add model specific global metadata to file',ncfile,' is',t01-t00,' seconds',flush=printFlush)


# for cice files, reset the cell_measures, add standard names and update cell_methods (where known)
        if ( ("cice" in ncfile) or cice_pattern.search(ncfile)):
            print ('found cice file ', ncfile)
            for var in nc.variables:
                v = nc.variables[var]
                try:
                    cell_measures = v.getncattr('cell_measures')
                    #print ('file: ', ncfile, 'var: ', var, 'cell_measures was: ', cell_measures)
                    v.setncattr('cell_measures', "area: areacello")
                    #print ('file: ', ncfile, 'var: ', var, 'cell_measures changed to: ', cell_measures)
                except AttributeError:
                    pass

                if (var in cice_map.keys()):
                   if (len(cice_map[var][0]) > 0):
                       #print ('var: ', var, 'cice_map_keys: ', cice_map.keys())
                       print ('adding standard_name for ', var, '-', cice_map[var][0])
                       v.setncattr('standard_name', cice_map[var][0])
                       #print ('var: ', var, 'standard_name: ', cice_map[var])
                       print ('adding cell methods for ', var, '-', cice_map[var][1])
                       cell_methods = v.getncattr('cell_methods')
                       print ('cice cell_methods ', cell_methods, 'area not in cell_methods: ', "area" not in cell_methods)
                       if ((len(cice_map[var][1]) > 0) and "area" not in cell_methods ):
                            updated_cell_methods = cice_map[var][1] + " " + cell_methods
                            v.setncattr('cell_methods', updated_cell_methods)

            fix_ice_indices(ncfile, nc)

# for nemo files, add area cell_methods where known
        if (nemo_pattern.search(ncfile)):
             print('found nemo file ', ncfile)
             for var in nc.variables:
                v = nc.variables[var]
                if (var in nemo_map.keys()):
                   if (len(nemo_map[var]) > 0):
                       cell_methods = v.getncattr('cell_methods')
                       print ('nemo cell_methods ', cell_methods, 'area not in cell_methods: ', "area" not in cell_methods)
                       if ((len(nemo_map[var]) > 0) and "area" not in cell_methods ):
                            updated_cell_methods = nemo_map[var] + " " + cell_methods
                            v.setncattr('cell_methods', updated_cell_methods)
                            print ('adding cell methods for ', var, '-', nemo_map[var])

             fix_ocean_indices(ncfile, nc)

# for atmosphere u, v, and t grid files fix hybrid heights
        atmos_pattern = atmos_hybrid_height_pattern
        if (atmos_pattern.search(ncfile)):
             print ('found atmos grid u, v, t file ', ncfile)
             fix_heights(ncfile, nc)
        else:
             print( 'no height fix for ', ncfile)

# for atmosphere u, v, zonal grid files fix hybrid heights
        if atmos_hybrid_height_pattern_2 is not None:
            atmos_pattern = atmos_hybrid_height_zonal_pattern
            if (atmos_pattern.search(ncfile)):
                print ('found atmos grid u, v, zonal file ', ncfile)
                fix_heights(ncfile, nc)
            else:
                print( 'no height fix for ', ncfile)

# for special case of D1TH
        if atmos_hybrid_height_pattern_3 is not None:
            atmos_pattern = re.compile(r'hrs')
            if (atmos_pattern.search(ncfile)):
                print ('found hrs ', ncfile)
                fix_heights(ncfile, nc)
            else:
                print( 'no height fix for ', ncfile)

# for cordex u, v, and t grid files fix hybrid heights
        atmos_pattern = cordex_pattern
        if (atmos_pattern.search(ncfile)):
             print ('found cordex grid u, v, t file ', ncfile)
             fix_heights(ncfile, nc)
        else:
             print( 'no height fix for ', ncfile)

# fix zonal means
        if(zonal_pattern.search(ncfile)):
             print ('found zonal file ', ncfile)
             fix_zmeans(ncfile, nc)
        else:
             print ( 'no zonal fix for ', ncfile)

        if (nc.isopen()):
            nc.close()
            print ('NetCDF file',ncfile,'closed\n',flush=printFlush)

        ens_num = os.environ['ENSEMBLE_NUM']
        if ("cice" in ncfile):
            new_fname = ncfile.replace('cice_', '')
            new_fname = new_fname.replace('_1d_', '_day_')
            new_fname = new_fname.replace('_1m_', '_mon_')
            print('Renaming {} to {}'.format(ncfile, new_fname))
            try:
                os.rename(ncfile, new_fname)
            except OSError:
                sys.exit('Failed to rename file: {}'.format(ncfile))

        t1 = time.perf_counter()
        print ('Time to modify file',ncfile,' =',t1-t0,' seconds',flush=printFlush)

if __name__ == '__main__':
    t0 = time.perf_counter()
    main()
    t1 = time.perf_counter()
    print ('Time in main =',t1-t0,' seconds',flush=printFlush)

