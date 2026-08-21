#!/usr/bin/env python
"""

NOTE - adapted from CANARI suite for N512-ORCA12 - it does not have any wider applicability
       height definitions are specifically for '$UMDIR/vn$VN/ctldata/vert/vertlevs_L85_50t_35s_85km'

       adds fields and metadata for hydbrid heights.
       special case handled for cordex u, v winds

       make sure that the grid variables in the file are covered by the cases below

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


# Orography files for T, U, V grids (N512)
orog_t_file = "/work/n02/n02/annette/EPOC/orog/N512/orog_T.nc"
orog_u_file = "/work/n02/n02/annette/EPOC/orog/N512/orog_U.nc"
orog_v_file = "/work/n02/n02/annette/EPOC/orog/N512/orog_V.nc"
orog_variable = "UM_m01s00i033_vn1106"


# File patterns
cordex_t_pattern = "t_pt_cordex"
cordex_u_pattern = "u_pt_cordex"
cordex_v_pattern = "v_pt_cordex"
zonal_day_u_pattern = "u_day_z_"
zonal_day_v_pattern = "v_day_z_"
monthly_t_pattern = "_mon_t_"
monthly_u_pattern = "_mon_u_"
monthly_v_pattern = "_mon_v_"


# 3D grids in data files
# Check that this covers all cases

verts  = {"um_atmos_DALLRH":      "rho",
          "um_atmos_DALLTH":      "theta",
          "um_atmos_DALLTHZ":     "theta",
          "um_atmos_DTHSPARSE":   "theta",
          "um_atmos_DALLRHP1":    "rho",
          "um_atmos_DRHP1SPARSE": "rho",
          "um_atmos_DALLTHSW":    "theta",
          "um_atmos_DALLTHLW":    "theta",
          "um_atmos_D1TH":        "theta",
          "um_atmos_D52RH":       "rho",
          "um_atmos_D52TH":       "theta",
          "um_atmos_DNOGWTH":     "theta",
          "um_atmos_DNOGWRH":     "rho",
          "um_atmos_DPBLRH":      "rho",
          "um_atmos_DPBLTH":      "theta"}

horzs  = {"lat_um_atmos_grid_t":              ["grid_t", "lon_um_atmos_grid_t"],
          "lat_um_atmos_grid_cu":             ["grid_u", "lon_um_atmos_grid_cu"],
          "lat_um_atmos_grid_cv":             ["grid_v", "lon_um_atmos_grid_cv"],
          "lat_um_atmos_grid_cu_halo_single": ["grid_u", "lon_um_atmos_grid_cu_halo_single"],
          "lat_um_atmos_grid_cv_halo_single": ["grid_v", "lon_um_atmos_grid_cv_halo_single"],
          "lat_um_atmos_grid_t_halo_single":  ["grid_t", "lon_um_atmos_grid_t_halo_single"],
          "lat_um_atmos_grid_t_halo_extended":["grid_t", "lon_um_atmos_grid_t_halo_extended"],
          "lat_cdex_grid_t"                  :["grid_t", "lon_cdex_grid_t"],
          "lat_cdex_grid_u"                  :["grid_u", "lon_cdex_grid_u"],
          "lat_cdex_grid_v"                  :["grid_v", "lon_cdex_grid_v"],
          "lat_zonl_grid_u"                  :["grid_u", "lon_zonl_grid_u"],
          "lat_zonl_grid_v"                  :["grid_v", "lon_zonl_grid_v"]}

## L85 grid definition

lev_bnds_theta_85_lin = np.array([0, 36.6666717529297, 36.6666717529297, 76.6666717529297, 76.6666717529297, 130.000015258789, 130.000015258789, 196.666625976562, 196.666625976562, 276.666656494141, 276.666656494141, 370, 370, 476.666656494141, 476.666656494141, 596.666564941406, 596.666564941406, 730, 730, 876.667053222656, 876.667053222656, 1036.66674804688, 1036.66674804688, 1209.99963378906, 1209.99963378906, 1396.66650390625, 1396.66650390625, 1596.66638183594, 1596.66638183594, 1810.00024414062, 1810.00024414062, 2036.66625976562, 2036.66625976562, 2276.66625976562, 2276.66625976562, 2529.99951171875, 2529.99951171875, 2796.66650390625, 2796.66650390625, 3076.66674804688, 3076.66674804688, 3370, 3370, 3676.66650390625, 3676.66650390625, 3996.666015625, 3996.666015625, 4330.00048828125, 4330.00048828125, 4676.6669921875, 4676.6669921875, 5036.66650390625, 5036.66650390625, 5409.9990234375, 5409.9990234375, 5796.666015625, 5796.666015625, 6196.66650390625, 6196.66650390625, 6609.99951171875, 6609.99951171875, 7036.66650390625, 7036.66650390625, 7476.66650390625, 7476.66650390625, 7930, 7930, 8396.66796875, 8396.66796875, 8876.6689453125, 8876.6689453125, 9370.0087890625, 9370.0087890625, 9876.6943359375, 9876.6943359375, 10396.7236328125, 10396.7236328125, 10930.1240234375, 10930.1240234375, 11476.904296875, 11476.904296875, 12037.087890625, 12037.087890625, 12610.736328125, 12610.736328125, 13197.9072265625, 13197.9072265625, 13798.6787109375, 13798.6787109375, 14413.177734375, 14413.177734375, 15041.5576171875, 15041.5576171875, 15684.0302734375, 15684.0302734375, 16340.859375, 16340.859375, 17012.40234375, 17012.40234375, 17699.099609375, 17699.099609375, 18401.49609375, 18401.49609375, 19120.291015625, 19120.291015625, 19856.33203125, 19856.33203125, 20610.65625, 20610.65625, 21384.521484375, 21384.521484375, 22179.44921875, 22179.44921875, 22997.27734375, 22997.27734375, 23840.171875, 23840.171875, 24710.69921875, 24710.69921875, 25611.91015625, 25611.91015625, 26547.353515625, 26547.353515625, 27521.189453125, 27521.189453125, 28538.248046875, 28538.248046875, 29604.123046875, 29604.123046875, 30725.28125, 30725.28125, 31909.119140625, 31909.119140625, 33164.15234375, 33164.15234375, 34500.0625, 34500.0625, 35927.88671875, 35927.88671875, 37460.13671875, 37460.13671875, 39110.98046875, 39110.98046875, 40896.390625, 40896.390625, 42834.33984375, 42834.33984375, 44945.015625, 44945.015625, 47251.0234375, 47251.0234375, 49777.58984375, 49777.58984375, 52552.890625, 52552.890625, 55608.22265625, 55608.22265625, 58978.35546875, 58978.35546875, 62701.83203125, 62701.83203125, 66821.2421875, 66821.2421875, 71383.640625, 71383.640625, 76440.890625, 76440.890625, 82050.0078125, 82050.0078125, 87949.9921875 ])

lev_bnds_rho_86_lin = np.array([0, 19.9999980926514, 19.9999980926514, 53.3333358764648, 53.3333358764648, 100.000038146973, 100.000038146973, 160, 160, 233.33332824707, 233.33332824707, 320, 320, 419.999969482422, 419.999969482422, 533.333374023438, 533.333374023438, 659.999938964844, 659.999938964844, 799.999938964844, 799.999938964844, 953.333679199219, 953.333679199219, 1120, 1120, 1300.00024414062, 1300.00024414062, 1493.33349609375, 1493.33349609375, 1700, 1700, 1919.99951171875, 1919.99951171875, 2153.3330078125, 2153.3330078125, 2399.99975585938, 2399.99975585938, 2659.99926757812, 2659.99926757812, 2933.3330078125, 2933.3330078125, 3219.99975585938, 3219.99975585938, 3519.99951171875, 3519.99951171875, 3833.33349609375, 3833.33349609375, 4160.00048828125, 4160.00048828125, 4499.99951171875, 4499.99951171875, 4853.33349609375, 4853.33349609375, 5219.99951171875, 5219.99951171875, 5599.99951171875, 5599.99951171875, 5993.3330078125, 5993.3330078125, 6399.99951171875, 6399.99951171875, 6819.99951171875, 6819.99951171875, 7253.3330078125, 7253.3330078125, 7699.99951171875, 7699.99951171875, 8160.0009765625, 8160.0009765625, 8633.33984375, 8633.33984375, 9120.0068359375, 9120.0068359375, 9620.01953125, 9620.01953125, 10133.3681640625, 10133.3681640625, 10660.0791015625, 10660.0791015625, 11200.1611328125, 11200.1611328125, 11753.638671875, 11753.638671875, 12320.5458984375, 12320.5458984375, 12900.9345703125, 12900.9345703125, 13494.880859375, 13494.880859375, 14102.4775390625, 14102.4775390625, 14723.87890625, 14723.87890625, 15359.236328125, 15359.236328125, 16008.8154296875, 16008.8154296875, 16672.90234375, 16672.90234375, 17351.900390625, 17351.900390625, 18046.291015625, 18046.291015625, 18756.703125, 18756.703125, 19483.88671875, 19483.88671875, 20228.775390625, 20228.775390625, 20992.52734375, 20992.52734375, 21776.5078125, 21776.5078125, 22582.392578125, 22582.392578125, 23412.162109375, 23412.162109375, 24268.1796875, 24268.1796875, 25153.224609375, 25153.224609375, 26070.587890625, 26070.587890625, 27024.109375, 27024.109375, 28018.26171875, 28018.26171875, 29058.2265625, 29058.2265625, 30150.017578125, 30150.017578125, 31300.53515625, 31300.53515625, 32517.7109375, 32517.7109375, 33810.59375, 33810.59375, 35189.5234375, 35189.5234375, 36666.23828125, 36666.23828125, 38254.02734375, 38254.02734375, 39967.92578125, 39967.92578125, 41824.8515625, 41824.8515625, 43843.83203125, 43843.83203125, 46046.20703125, 46046.20703125, 48455.83203125, 48455.83203125, 51099.34765625, 51099.34765625, 54006.42578125, 54006.42578125, 57210.015625, 57210.015625, 60746.703125, 60746.703125, 64656.95703125, 64656.95703125, 68985.5234375, 68985.5234375, 73781.765625, 73781.765625, 79100.015625, 79100.015625, 85000, 85000, 90899.98437520 ])

b_bnds_theta_85_lin = np.array([1, 0.995860934257507, 0.995860934257507, 0.991355419158936, 0.991355419158936, 0.985363960266113, 0.985363960266113, 0.977900147438049, 0.977900147438049, 0.968980967998505, 0.968980967998505, 0.958626985549927, 0.958626985549927, 0.946861922740936, 0.946861922740936, 0.93371307849884, 0.93371307849884, 0.919211089611053, 0.919211089611053, 0.903389930725098, 0.903389930725098, 0.886287212371826, 0.886287212371826, 0.867943704128265, 0.867943704128265, 0.848403632640839, 0.848403632640839, 0.827714681625366, 0.827714681625366, 0.805927932262421, 0.805927932262421, 0.783098042011261, 0.783098042011261, 0.75928258895874, 0.75928258895874, 0.734543085098267, 0.734543085098267, 0.708944141864777, 0.708944141864777, 0.682553827762604, 0.682553827762604, 0.655443787574768, 0.655443787574768, 0.627688825130463, 0.627688825130463, 0.599367320537567, 0.599367320537567, 0.570560812950134, 0.570560812950134, 0.541354656219482, 0.541354656219482, 0.511837363243103, 0.511837363243103, 0.482100784778595, 0.482100784778595, 0.452240228652954, 0.452240228652954, 0.422354459762573, 0.422354459762573, 0.392545729875565, 0.392545729875565, 0.362919509410858, 0.362919509410858, 0.333584785461426, 0.333584785461426, 0.304653882980347, 0.304653882980347, 0.276242583990097, 0.276242583990097, 0.248470112681389, 0.248470112681389, 0.221458733081818, 0.221458733081818, 0.195334210991859, 0.195334210991859, 0.170226037502289, 0.170226037502289, 0.146266028285027, 0.146266028285027, 0.123590461909771, 0.123590461909771, 0.102338522672653, 0.102338522672653, 0.0826521068811417, 0.0826521068811417, 0.0646774247288704, 0.0646774247288704, 0.0485646799206734, 0.0485646799206734, 0.0344676785171032, 0.0344676785171032, 0.0225453991442919, 0.0225453991442919, 0.01296216994524, 0.01296216994524, 0.00588912842795253, 0.00588912842795253, 0.00150532135739923, 0.00150532135739923, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 ])

b_bnds_rho_86_lin = np.array([1, 0.997741281986237, 0.997741281986237, 0.993982434272766, 0.993982434272766, 0.988731920719147, 0.988731920719147, 0.982001721858978, 0.982001721858978, 0.973807096481323, 0.973807096481323, 0.964166879653931, 0.964166879653931, 0.953103065490723, 0.953103065490723, 0.940641283988953, 0.940641283988953, 0.926810503005981, 0.926810503005981, 0.911642968654633, 0.911642968654633, 0.895174443721771, 0.895174443721771, 0.877444267272949, 0.877444267272949, 0.858494758605957, 0.858494758605957, 0.838372051715851, 0.838372051715851, 0.81712543964386, 0.81712543964386, 0.7948077917099, 0.7948077917099, 0.77147513628006, 0.77147513628006, 0.747187197208405, 0.747187197208405, 0.722006916999817, 0.722006916999817, 0.696000635623932, 0.696000635623932, 0.669238269329071, 0.669238269329071, 0.641793012619019, 0.641793012619019, 0.613741397857666, 0.613741397857666, 0.585163474082947, 0.585163474082947, 0.556142747402191, 0.556142747402191, 0.526765942573547, 0.526765942573547, 0.49712336063385, 0.49712336063385, 0.467308610677719, 0.467308610677719, 0.437418729066849, 0.437418729066849, 0.40755420923233, 0.40755420923233, 0.377818822860718, 0.377818822860718, 0.348319888114929, 0.348319888114929, 0.319168090820312, 0.319168090820312, 0.290477395057678, 0.290477395057678, 0.262365132570267, 0.262365132570267, 0.234952658414841, 0.234952658414841, 0.20836341381073, 0.20836341381073, 0.182725623250008, 0.182725623250008, 0.158169254660606, 0.158169254660606, 0.134828746318817, 0.134828746318817, 0.112841464579105, 0.112841464579105, 0.0923482477664948, 0.0923482477664948, 0.0734933465719223, 0.0734933465719223, 0.0564245767891407, 0.0564245767891407, 0.041294027119875, 0.041294027119875, 0.028257654979825, 0.028257654979825, 0.0174774676561356, 0.0174774676561356, 0.00912047084420919, 0.00912047084420919, 0.00336169824004173, 0.00336169824004173, 0.000384818413294852, 0.000384818413294852, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 ])

lev_t_85 = np.array([19.9999980926514, 53.3333358764648, 100.000038146973, 160,
                     233.33332824707, 320, 419.999969482422, 533.333374023438,
                     659.999938964844, 799.999938964844, 953.333679199219, 1120,
                     1300.00024414062, 1493.33349609375, 1700, 1919.99951171875,
                     2153.3330078125, 2399.99975585938, 2659.99926757812, 2933.3330078125,
                     3219.99975585938, 3519.99951171875, 3833.33349609375, 4160.00048828125,
                     4499.99951171875, 4853.33349609375, 5219.99951171875, 5599.99951171875,
                     5993.3330078125, 6399.99951171875, 6819.99951171875, 7253.3330078125,
                     7699.99951171875, 8160.0009765625, 8633.33984375, 9120.0068359375,
                     9620.01953125, 10133.3681640625, 10660.0791015625, 11200.1611328125,
                     11753.638671875, 12320.5458984375, 12900.9345703125, 13494.880859375,
                     14102.4775390625, 14723.87890625, 15359.236328125, 16008.8154296875,
                     16672.90234375, 17351.900390625, 18046.291015625, 18756.703125,
                     19483.88671875, 20228.775390625, 20992.52734375, 21776.5078125,
                     22582.392578125, 23412.162109375, 24268.1796875, 25153.224609375,
                     26070.587890625, 27024.109375, 28018.26171875, 29058.2265625,
                     30150.017578125, 31300.53515625, 32517.7109375, 33810.59375,
                     35189.5234375, 36666.23828125, 38254.02734375, 39967.92578125,
                     41824.8515625, 43843.83203125, 46046.20703125, 48455.83203125,
                     51099.34765625, 54006.42578125, 57210.015625, 60746.703125,
                     64656.95703125, 68985.5234375, 73781.765625, 79100.015625, 85000 ])

lev_r_86 = np.array([10.0000038146973, 36.6666717529297, 76.6666717529297,
                     130.000015258789, 196.666625976562, 276.666656494141, 370,
                     476.666656494141, 596.666564941406, 730, 876.667053222656,
                     1036.66674804688, 1209.99963378906, 1396.66650390625, 1596.66638183594,
                     1810.00024414062, 2036.66625976562, 2276.66625976562, 2529.99951171875,
                     2796.66650390625, 3076.66674804688, 3370, 3676.66650390625,
                     3996.666015625, 4330.00048828125, 4676.6669921875, 5036.66650390625,
                     5409.9990234375, 5796.666015625, 6196.66650390625, 6609.99951171875,
                     7036.66650390625, 7476.66650390625, 7930, 8396.66796875, 8876.6689453125,
                     9370.0087890625, 9876.6943359375, 10396.7236328125, 10930.1240234375,
                     11476.904296875, 12037.087890625, 12610.736328125, 13197.9072265625,
                     13798.6787109375, 14413.177734375, 15041.5576171875, 15684.0302734375,
                     16340.859375, 17012.40234375, 17699.099609375, 18401.49609375,
                     19120.291015625, 19856.33203125, 20610.65625, 21384.521484375,
                     22179.44921875, 22997.27734375, 23840.171875, 24710.69921875,
                     25611.91015625, 26547.353515625, 27521.189453125, 28538.248046875,
                     29604.123046875, 30725.28125, 31909.119140625, 33164.15234375,
                     34500.0625, 35927.88671875, 37460.13671875, 39110.98046875, 40896.390625,
                     42834.33984375, 44945.015625, 47251.0234375, 49777.58984375,
                     52552.890625, 55608.22265625, 58978.35546875, 62701.83203125,
                     66821.2421875, 71383.640625, 76440.890625, 82050.0078125, 87949.993])

b_t_85 = np.array([0.997741281986237, 0.993982434272766, 0.988731920719147,
                   0.982001721858978, 0.973807096481323, 0.964166879653931,
                   0.953103065490723, 0.940641283988953, 0.926810503005981,
                   0.911642968654633, 0.895174443721771, 0.877444267272949,
                   0.858494758605957, 0.838372051715851, 0.81712543964386, 0.7948077917099,
                   0.77147513628006, 0.747187197208405, 0.722006916999817,
                   0.696000635623932, 0.669238269329071, 0.641793012619019,
                   0.613741397857666, 0.585163474082947, 0.556142747402191,
                   0.526765942573547, 0.49712336063385, 0.467308610677719,
                   0.437418729066849, 0.40755420923233, 0.377818822860718,
                   0.348319888114929, 0.319168090820312, 0.290477395057678,
                   0.262365132570267, 0.234952658414841, 0.20836341381073,
                   0.182725623250008, 0.158169254660606, 0.134828746318817,
                   0.112841464579105, 0.0923482477664948, 0.0734933465719223,
                   0.0564245767891407, 0.041294027119875, 0.028257654979825,
                   0.0174774676561356, 0.00912047084420919, 0.00336169824004173,
                   0.000384818413294852, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                   0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 ])

b_r_86 = np.array([0.998870313167572, 0.995860934257507, 0.991355419158936,
                   0.985363960266113, 0.977900147438049, 0.968980967998505,
                   0.958626985549927, 0.946861922740936, 0.93371307849884,
                   0.919211089611053, 0.903389930725098, 0.886287212371826,
                   0.867943704128265, 0.848403632640839, 0.827714681625366,
                   0.805927932262421, 0.783098042011261, 0.75928258895874,
                   0.734543085098267, 0.708944141864777, 0.682553827762604,
                   0.655443787574768, 0.627688825130463, 0.599367320537567,
                   0.570560812950134, 0.541354656219482, 0.511837363243103,
                   0.482100784778595, 0.452240228652954, 0.422354459762573,
                   0.392545729875565, 0.362919509410858, 0.333584785461426,
                   0.304653882980347, 0.276242583990097, 0.248470112681389,
                   0.221458733081818, 0.195334210991859, 0.170226037502289,
                   0.146266028285027, 0.123590461909771, 0.102338522672653,
                   0.0826521068811417, 0.0646774247288704, 0.0485646799206734,
                   0.0344676785171032, 0.0225453991442919, 0.01296216994524,
                   0.00588912842795253, 0.00150532135739923, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                   0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])

BNDS = 2


def fix_heights(diagnostics_file, g):

# reshape the bounds arrays
    lev_bnds_theta_85 = np.reshape(lev_bnds_theta_85_lin, (-1, 2))
    lev_bnds_rho_86   = np.reshape(lev_bnds_rho_86_lin,   (-1, 2))
    b_bnds_theta_85   = np.reshape(b_bnds_theta_85_lin,   (-1, 2))
    b_bnds_rho_86     = np.reshape(b_bnds_rho_86_lin,     (-1, 2))

# read the orography files for u, v, and t grids
    orog_u_f = netCDF4.Dataset(orog_u_file, "r", format="NETCDF4")
    orog_u   = orog_u_f.variables[orog_variable]
    orog_v_f = netCDF4.Dataset(orog_v_file, "r", format="NETCDF4")
    orog_v   = orog_v_f.variables[orog_variable]
    orog_t_f = netCDF4.Dataset(orog_t_file, "r", format="NETCDF4")
    orog_t   = orog_t_f.variables[orog_variable]


#copy diagnostics file for safety
    temp_diags_file = diagnostics_file + '_being_worked_on'
    try:
        shutil.copyfile(diagnostics_file, temp_diags_file)
        print ( 'copy succeeded: ', temp_diags_file, flush=True)
    except:
        print ( 'copy failed: ', temp_diags_file, flush=True)
        sys.exit(1)
#    g = netCDF4.Dataset(diagnostics_file, "a", format="NETCDF4")


# placeholder for information about vertical coords and which horizontal grid they are attached to
# there should be only one horizontal grid for a given vertical coordinate
    height_domains = []
    hd             = {}

    cdex           = False
    zonal          = False

# loop through fields
    for v in g.variables:
#        print(v)
        v_dims = g.variables[v].dimensions
        if (len(v_dims) == 4):      #  we are interested in fields that have (time, vertical, lat, lon) type coords
            if (v_dims[1] in verts):
                print(v_dims[1], v_dims[2])

#               this test has become a bit of a mess because XIOS does not handle coordinate names as needed
#               so we need to rely on file names to know which grid type to consider

                if(v_dims[2] == 'lat'):
                    # check for cordex data
                    if (cordex_t_pattern in diagnostics_file):
                        print ('t_pt_cordex in', diagnostics_file)
                        lat = "lat_cdex_grid_t"
                        cdex = True
                    elif (cordex_u_pattern in diagnostics_file):
                        print ('u_pt_cordex in', diagnostics_file)
                        lat = "lat_cdex_grid_u"
                        cdex = True
                    elif (cordex_v_pattern in diagnostics_file):
                        print ('v_pt_cordex in', diagnostics_file)
                        lat = "lat_cdex_grid_v"
                        cdex = True
                    # check for zonal data
                    elif (zonal_day_u_pattern in diagnostics_file):
                        print ('_z_', diagnostics_file)
                        lat = "lat_zonl_grid_u"
                        zonal = True
                    elif (zonal_day_v_pattern in diagnostics_file):
                        print ('_z_', diagnostics_file)
                        lat = "lat_zonl_grid_v"
                        zonal = True
                    elif (monthly_t_pattern in diagnostics_file or 'hrs' in diagnostics_file):
                        lat = "lat_um_atmos_grid_t"
                    elif (monthly_u_pattern in diagnostics_file):
                        lat = "lat_um_atmos_grid_cu"
                    elif (monthly_v_pattern in diagnostics_file):
                        lat = "lat_um_atmos_grid_cv"
                    else:
                        print ("ERROR in v_dims")
                        sys.exit(1)
                else:
                    lat = v_dims[2]

                print (height_domains)
                if ([v_dims[1], horzs[lat][0]] not in height_domains):
                    height_domains.append([v_dims[1], horzs[lat][0]])  # entries like [um-atmos_DALLRH, lat_um-atmos_grid_t, grid_t]
                    hd[v_dims[1]] = [horzs[lat][0], lat, horzs[lat][1]]

        if (len(v_dims) == 5):      #  we are interested in fields that have (time, pseudo, vertical, lat, lon) type coords
            if (v_dims[2] in verts):
                print(v_dims[2], v_dims[3])

                if ([v_dims[2], horzs[lat][0]] not in height_domains):
                    height_domains.append([v_dims[2], horzs[lat][0]])  # entries like [um-atmos_DALLRH, lat_um-atmos_grid_t, grid_t]
                    hd[v_dims[2]] = [horzs[lat][0], lat, horzs[lat][1]]


    print(height_domains)
    print (hd)


    for x in hd:

        print (x)
        print (hd[x])
#        print (g.variables[x][:])

# need a check to proceed or not
# if the verical coordinate has attributes units metres - it is not in model levels, so skip

        if (g.variables[x].getncattr('units') == "m"):
            print ("skipping ", x, "assuming already converted to hybrid heights")
            continue

# create the bnds dimension
        if ("bnds" not in g.dimensions):
            g.createDimension("bnds", BNDS)

# simple test for the extra rho level
        if (g.variables[x][-1] > 85):
            extra_level = True
        else:
            extra_level = False

        print ('extra_level ', extra_level)

# determine which kind of vertical coord and set lev, b, and bounds sources
        if (verts[x] == "theta"):
            lev      = lev_t_85
            bee      = b_t_85
            lev_bnds = lev_bnds_theta_85
            b_bnds   = b_bnds_theta_85
        elif (verts[x] == "rho"):
            if (extra_level == True):
                lev      = lev_r_86
                bee      = b_r_86
                lev_bnds = lev_bnds_rho_86
                b_bnds   = b_bnds_rho_86
            else:
                lev      = lev_r_86[0:85]
                bee      = b_r_86[0:85]
                lev_bnds = lev_bnds_rho_86[0:85]
                b_bnds   = b_bnds_rho_86[0:85]
        else:
            print("ERROR - unknown vertical coord")
            sys.exit(1)

# determine which grid and set orog
        if (hd[x][0] == "grid_t"):
            add_orog      = orog_t
            b_type        = 'b_t_' + x
            b_bnds_type   = 'b_bnds_t_' + x
            lev_bnds_type = 'lev_bnds_t_' + x
            orog_type = "orog_t"
        elif (hd[x][0] == "grid_u"):
            add_orog      = orog_u
            b_type        = 'b_u_' + x
            b_bnds_type   = 'b_bnds_u_' + x
            lev_bnds_type = 'lev_bnds_u_' + x
            orog_type = "orog_u"
        elif (hd[x][0] == "grid_v"):
            add_orog      = orog_v
            b_type        = 'b_v_' + x
            b_bnds_type   = 'b_bnds_v_' + x
            lev_bnds_type = 'lev_bnds_v_' + x
            orog_type     = "orog_v"
        else:
            print("ERROR - unknown grid")
            sys.exit(1)

#        print ("vertical grid", x[0], g.variables[x[0]][:], g.variables[x[0]][-1])

        print ("grid type is ", hd[x][0])
        print ("vert grid type is ", verts[x])

#  add metadata for formula terms, add b and orog appropriately
        print('adding metadata for ', x, 'for ', hd[x][0])

        model_levels=[]      # somewhere to keep the model level numbers

# fix up the lev coordinates
        if (g.variables[x]):
            print ('fixing level number with lev')
# only fix up the levels needed  (a bit fortran-like)
            ind = 0
            for model_level in g.variables[x]:
# keep model level number - needed later for the bs and bounds
                model_levels.append(model_level)
#                print ("model level ", model_level, lev[int(model_level)-1])
                g.variables[x][ind] = lev[int(model_level)-1]
                ind = ind + 1

# add variables to g
        if (b_type not in g.variables):
            print('create b with ', x)
            print('create b_bnds with ', x)
            print('create lev_bnds with ', x)

            b = g.createVariable(b_type, "f8", (x,))
            b.setncattr("long_name", "vertical coordinate formula term: b(k)")

            b_bounds = g.createVariable(b_bnds_type, "f8", (x, "bnds"))
            b_bounds.setncattr("long_name", "vertical coordinate formula term: b(k+1/2)")
#            print("b_bounds", b_bounds)

            lev_bounds = g.createVariable(lev_bnds_type, "f8", (x, "bnds"))
            lev_bounds.setncattr("formula",  "z = a + b*orog")
            lev_bounds.setncattr("standard_name", "atmosphere_hybrid_height_coordinate")
            lev_bounds.setncattr("units", "m")
            f_terms = 'a: ' + lev_bnds_type + ' b: ' + b_bnds_type + ' orog: ' + orog_type
            lev_bounds.setncattr("formula_terms", f_terms)

# add b data
        if (b_type in g.variables):
            print ('add b values for;', b_type)
            print ('add b_bnd values for;', b_type)
            print ('add lev_bnd values for;', b_type)
            ind = 0
            for model_level in g.variables[b_type]:
                g.variables[b_type][ind]        = bee[int(model_levels[ind]-1)]
                g.variables[b_bnds_type][ind]   = b_bnds[int(model_levels[ind]-1)]
                g.variables[lev_bnds_type][ind] = lev_bnds[int(model_levels[ind]-1)]
                ind = ind + 1

        print ('got here')

# add orography
        if (orog_type not in g.variables):
            if (cdex == True or zonal == True):
                orog = g.createVariable(orog_type, "f8", ("lat", "lon"))
            else:
#                orog = g.createVariable(orog_type, "f8", (hd[x][1], hd[x][2]))
                orog = g.createVariable(orog_type, "f8", ("lat", "lon"))
            orog.setncattr("long_name", "Surface Altitude")
            orog.setncattr("standard_name", "surface_altitude")
            orog.setncattr("units", "m")

        if(orog_type in g.variables):
            print ('add orog values;')
            orog = g.variables[orog_type]
            orog[:] = add_orog[:]

# add formula terms to our height coordinate
        print ('finally, adding formula terms to ', x)
        v = g.variables[x]
        terms = 'z = a + b*orog'
        print("formula", terms)
        v.setncattr("formula", terms)
        f_terms = 'a: '+ x + ' b: '+ b_type + ' orog: ' + orog_type
        print("formula", f_terms)
        v.setncattr("formula_terms", f_terms)

# fix the attributes
        v.setncattr("long_name", "hybrid height coordinate")
        v.setncattr("standard_name", "atmosphere_hybrid_height_coordinate")
        v.setncattr("computed_standard_name", "altitude")
        v.setncattr("units", "m")
        v.setncattr("bounds", lev_bnds_type)

# remove the copied diagnostics file
    os.remove(temp_diags_file)

# close files
    orog_u_f.close()
    orog_v_f.close()
    orog_t_f.close()


def main():

    # Test
    ncfile = '/work/n02/n02/annette/EPOC/cs488a_mon_v_195001-195001.nc'
    nc = netCDF4.Dataset(ncfile,'a')
    fix_heights(ncfile, nc)
    nc.close()


if __name__ == '__main__':

    main()

