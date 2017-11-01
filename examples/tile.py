# coding=utf-8
from __future__ import print_function

import logging

from marblecutter import tiling
from marblecutter.catalogs.postgis import PostGISCatalog
from marblecutter.formats.geotiff import GeoTIFF
from mercantile import Tile

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    tile = Tile(324, 787, 11)
    (headers, data) = tiling.render_tile(
        tile, PostGISCatalog(), format=GeoTIFF(area_or_point="Point"), scale=2)

    print("headers: ", headers)

    with open("tmp/11_324_787.tif", "w") as f:
        f.write(data)
