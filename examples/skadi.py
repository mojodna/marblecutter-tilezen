# coding=utf-8
from __future__ import print_function

import logging

from marblecutter.catalogs.postgis import PostGISCatalog
from tilezen import skadi

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    tile = "N38W123"
    (headers, data) = skadi.render_tile(tile, PostGISCatalog())

    print("Headers: ", headers)

    with open("tmp/{}.hgt.gz".format(tile), "w") as f:
        f.write(data)
