#!/usr/bin/env python
"""

NOTE - adapted from CANARI suite for N512-ORCA12 - it does not have any wider applicability
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
nj = 3604
ni = 4320
nc = 5
nkice = 4
nksnow = 1


def fix_ice_indices(diagnostics_file, g):


# create the dimension variable
    if ("nj" not in g.dimensions):
       print("ERROR - unknown coord nj")
       sys.exit(1)

# add variables to g 
    if ("nj" not in g.variables):
       print('create nj')

       b = g.createVariable("nj", "f8", ("nj"))    
       b.setncattr("long_name", "cell index along second dimension")
       b.setncattr("units", "1")
       g.variables["nj"][:] = range(nj)

    if ("ni" not in g.dimensions):
       print("ERROR - unknown coord ni")
       sys.exit(1)

    if ("ni" not in g.variables):
       print('create ni')

       b = g.createVariable("ni", "f8", ("ni"))    
       b.setncattr("long_name", "cell index along first dimension")
       b.setncattr("units", "1")
       g.variables["ni"][:] = range(ni)

    if ("nc" not in g.dimensions):
       print("ERROR - unknown coord nc")
       sys.exit(1)

    if ("nc" not in g.variables):
       print('create nc')

       b = g.createVariable("nc", "f8", ("nc"))    
       b.setncattr("long_name", "cell index for ice categories")
       b.setncattr("units", "1")
       g.variables["nc"][:] = range(nc)

    if ("nkice" not in g.dimensions):
       print("ERROR - unknown coord nkice")
       sys.exit(1)

    if ("nkice" not in g.variables):
       print('create nkice')

       b = g.createVariable("nkice", "f8", ("nkice"))    
       b.setncattr("long_name", "cell index for ice internal temperatures")
       b.setncattr("units", "1")
       g.variables["nkice"][:] = range(nkice)

    if ("nksnow" not in g.dimensions):
       print("ERROR - unknown coord nksnow")
       sys.exit(1)

    if ("nksnow" not in g.variables):
       print('create nksnow')

       b = g.createVariable("nksnow", "f8", ("nksnow"))    
       b.setncattr("long_name", "cell index for snow levels")
       b.setncattr("units", "1")
       g.variables["nksnow"][:] = range(nksnow)


def main():

    # Test
    ncfile = '/work/n02/n02/annette/EPOC/cice_cs488i_1m_19500101-19500201.nc'
    nc = netCDF4.Dataset(ncfile,'a')
    fix_ice_indices(ncfile, nc)
    nc.close()



if __name__ == '__main__':

    main()

