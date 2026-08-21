#!/usr/bin/env python
"""

NOTE - adapted from CANARI for N512-ORCA12 - it does not have any wider applicability
       uses cf-python to create the zonal mean & overwrites the full field data

"""

import sys
import os
import shutil
import time
import re
import fnmatch
import netCDF4
import configparser
import uuid
import numpy as np
import random
import cf




def fix_zmeans(diagnostics_file, g):


# check if already zonally meaned
#    g = netCDF4.Dataset(diagnostics_file, "a", format="NETCDF4")
    if ("lon" not in g.dimensions):
        print ('lon not in dimensions for ', diagnostics_file)
        sys.exit(1)
    elif (len(g.dimensions['lon']) == 1):
        print ('do nothing - already zonally meaned ', diagnostics_file)
        return

# something doesn't play right between g and f -- close g first
    print ('close g', flush=True)
    g.close()

    print ('cf.read', flush=True)
    f=cf.read(diagnostics_file)

    print (f, flush=True)

    u_mean=[]
    for u in f:
        print ('individual fields from f', flush=True)
        print ('   ')
        print (u)
        v = u.collapse('mean', 'X')
        v.dtype = 'float32' 
        u_mean.append(v)
        
    print ('writing zonal means from ', diagnostics_file, flush=True)
    diagnostics_file_zonal = diagnostics_file + 'TESTZ'
    cf.write(u_mean, diagnostics_file_zonal, compress=1)
    
    os.rename(diagnostics_file_zonal, diagnostics_file)


def main():

    # Test
    ncfile = '/work/n02/n02/annette/EPOC/cs488a_mon_z_195001-195001.nc'
    nc = netCDF4.Dataset(ncfile,'a')
    fix_zmeans(ncfile, nc)


if __name__ == '__main__':

    main()

