# coding=utf-8
from __future__ import print_function

import logging

from mercantile import Tile

from marblecutter import tiling
from marblecutter.catalogs.postgis import PostGISCatalog
from marblecutter.formats.color_ramp import ColorRamp
from marblecutter.formats.geotiff import GeoTIFF
from tilezen.transformations import Hillshade

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    tile = Tile(1308, 3164, 13)

    hillshade = Hillshade(resample=True, add_slopeshade=True)
    (headers, data) = tiling.render_tile(
        tile,
        PostGISCatalog(),
        format=GeoTIFF(),
        transformation=hillshade,
        scale=1)

    print("Headers: ", headers)

    with open("tmp/{}_{}_{}_hillshade.tif".format(tile.z, tile.x, tile.y),
              "w") as f:
        f.write(data)

    (headers, data) = tiling.render_tile(
        tile, PostGISCatalog(), format=GeoTIFF())

    print("Headers: ", headers)

    with open("tmp/{}_{}_{}.tif".format(tile.z, tile.x, tile.y), "w") as f:
        f.write(data)

    # tile = Tile(654, 1582, 12)
    (headers, data) = tiling.render_tile(
        tile,
        PostGISCatalog(),
        format=ColorRamp("png"),
        transformation=hillshade,
        scale=2)

    print("Headers: ", headers)

    with open("tmp/{}_{}_{}_hillshade.png".format(tile.z, tile.x, tile.y),
              "w") as f:
        f.write(data)
