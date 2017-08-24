# coding=utf-8
from __future__ import print_function

import logging

from mercantile import Tile

from marblecutter import tiling
from marblecutter.catalogs.postgis import PostGISCatalog
from marblecutter.formats.png import PNG
from tilezen.transformations import Terrarium

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    tile = Tile(324, 787, 11)
    (headers, data) = tiling.render_tile(
        tile,
        PostGISCatalog(),
        format=PNG(),
        transformation=Terrarium(),
        scale=2)

    print("Headers: ", headers)

    with open("tmp/11_324_787_terrarium.png", "w") as f:
        f.write(data)
