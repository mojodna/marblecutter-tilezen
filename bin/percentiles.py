#!/usr/bin/env python
# coding=utf-8

from __future__ import print_function

import json
import os
import sys
import urllib

import numpy as np

import rasterio
from rio_toa import reflectance


def percentiles(input, band, meta_url):
    meta = json.load(urllib.urlopen(meta_url))

    with rasterio.Env():
        with rasterio.open(input) as src:
            data = src.read(indexes=1, out_shape=(1024, 1024))

            sun_elev = meta["L1_METADATA_FILE"]["IMAGE_ATTRIBUTES"][
                "SUN_ELEVATION"]
            multi_reflect = meta[
                "L1_METADATA_FILE"]["RADIOMETRIC_RESCALING"].get(
                    "REFLECTANCE_MULT_BAND_{}".format(band))
            add_reflect = meta[
                "L1_METADATA_FILE"]["RADIOMETRIC_RESCALING"].get(
                    "REFLECTANCE_ADD_BAND_{}".format(band))

            data = 10000 * reflectance.reflectance(
                data, multi_reflect, add_reflect, sun_elev, src_nodata=0)

            return np.percentile(data[data > 0], (2, 5, 95, 98)).tolist()


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(
            "usage: {} <input> <band> <meta url>".format(
                os.path.basename(sys.argv[0])),
            file=sys.stderr)
        exit(1)

    input, band, meta_url = sys.argv[1:]
    try:
        print(" ".join(map(str, percentiles(input, band, meta_url))))
    except IOError as e:
        print("Unable to open '{}': {}".format(input, e), file=sys.stderr)
        exit(1)
