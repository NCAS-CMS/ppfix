#!/usr/bin/env python
"""

NOTE - adapted from CANARI for N512-ORCA12 - it does not have any wider applicability
       fix missing index variables

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


# Grid dimensions (ORCA12)
x = 4322
y = 3606


def fix_ocean_indices(diagnostics_file, g):


# create the dimension variable
    if ("x" not in g.dimensions):
       print("ERROR - unknown coord x")
       sys.exit(1)

# add variables to g 
    if ("x" not in g.variables):
       print('create x')

       b = g.createVariable("x", "f8", ("x"))    
       b.setncattr("long_name", "cell index along first dimension")
       b.setncattr("units", "1")
       g.variables["x"][:] = range(x)

    if ("y" not in g.dimensions):
       print("ERROR - unknown coord y")
       sys.exit(1)

    if ("y" not in g.variables):
       print('create y')

       b = g.createVariable("y", "f8", ("y"))    
       b.setncattr("long_name", "cell index along second dimension")
       b.setncattr("units", "1")
       g.variables["y"][:] = range(y)


def main():

    # Test
    ncfile = '/work/n02/n02/annette/EPOC/cs488o_mon_grid_T_195001-195001.nc'
    nc = netCDF4.Dataset(ncfile,'a')
    fix_ocean_indices(ncfile, nc)
    nc.close()

if __name__ == '__main__':

    main()

