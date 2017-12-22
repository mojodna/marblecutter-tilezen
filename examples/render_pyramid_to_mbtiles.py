# coding=utf-8
from __future__ import print_function

import argparse
import logging
import os
import sqlite3

import mercantile
from marblecutter import get_resolution_in_meters, tiling
from marblecutter.catalogs import WGS84_CRS
from marblecutter.catalogs.postgis import PostGISCatalog
from marblecutter.formats.png import PNG
from marblecutter.stats import Timer
from marblecutter.transformations import Image
from marblecutter.utils import Bounds
from mercantile import Tile
from tilezen.catalogs import SpatialiteCatalog

logging.basicConfig(level=logging.INFO)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('marblecutter.mosaic').setLevel(logging.WARNING)
logger = logging.getLogger('batchtiler')

if os.environ.get('VERBOSE'):
    logger.setLevel(logging.DEBUG)

IMAGE_TRANSFORMATION = Image()
PNG_FORMAT = PNG()


class MbtilesOutput(object):
    def __init__(self, filename, **kwargs):
        self._filename = filename

    def _setup_mbtiles(self, cur):
        cur.execute("""
            CREATE TABLE tiles (
            zoom_level integer,
            tile_column integer,
            tile_row integer,
            tile_data blob);
            """)
        cur.execute("""
            CREATE TABLE metadata
            (name text, value text);
            """)
        cur.execute("""
            CREATE TABLE grids (
            zoom_level integer,
            tile_column integer,
            tile_row integer,
            grid blob);
            """)
        cur.execute("""
            CREATE TABLE grid_data (
            zoom_level integer,
            tile_column integer,
            tile_row integer,
            key_name text,
            key_json text);
            """)
        cur.execute("""
            CREATE UNIQUE INDEX name ON metadata (name);
            """)
        cur.execute("""
            CREATE UNIQUE INDEX tile_index ON tiles (
            zoom_level, tile_column, tile_row);
            """)

    def _optimize_connection(self, cur):
        cur.execute("""
            PRAGMA synchronous=0
            """)
        cur.execute("""
            PRAGMA locking_mode=EXCLUSIVE
            """)
        cur.execute("""
            PRAGMA journal_mode=DELETE
            """)

    def _flip_y(self, zoom, row):
        """
        mbtiles requires WMTS (origin in the upper left),
        and Tilezen stores in TMS (origin in the lower left).
        This adjusts the row/y value to match WMTS.
        """

        if row is None or zoom is None:
            raise TypeError("zoom and row cannot be null")

        return (2**zoom) - 1 - row

    def add_metadata(self, name, value):
        self._cur.execute("""
            INSERT INTO metadata (
                name, value
            ) VALUES (
                ?, ?
            );
            """, (name, value, ))

    def open(self):
        self._conn = sqlite3.connect(self._filename)
        self._cur = self._conn.cursor()
        self._optimize_connection(self._cur)
        self._setup_mbtiles(self._cur)

    def add_tile(self, tile, data):
        self._cur.execute("""
            INSERT INTO tiles (
                zoom_level, tile_column, tile_row, tile_data
            ) VALUES (
                ?, ?, ?, ?
            );
            """, (tile.z, tile.x, self._flip_y(tile.z, tile.y),
                  sqlite3.Binary(data), ))

    def close(self):
        self._conn.commit()
        self._conn.close()


def sources_for_tile(tile, catalog, min_zoom=None, max_zoom=None):
    """Render a tile's source footprints."""
    bounds = Bounds(mercantile.bounds(tile), WGS84_CRS)
    shape = (256, 256)
    resolution = get_resolution_in_meters(bounds, shape)

    return catalog.get_sources(
        bounds,
        resolution,
        min_zoom=min_zoom,
        max_zoom=max_zoom,
        include_geometries=True)


def build_catalog(tile, min_zoom, max_zoom):
    upstream_catalog = PostGISCatalog(table="imagery")
    catalog = SpatialiteCatalog()

    for source in sources_for_tile(
            tile, upstream_catalog, min_zoom=min_zoom, max_zoom=max_zoom):
        catalog.add_source(source)

    return catalog


def render_tile_exc_wrapper(tile, catalog, output):
    try:
        render_tile(tile, catalog, output)
    except Exception:
        logger.exception('Error while processing tile %s', tile)
        raise


def render_tile(tile, catalog, output):
    with Timer() as t:
        (headers, data) = tiling.render_tile(
            tile,
            catalog,
            format=PNG_FORMAT,
            transformation=IMAGE_TRANSFORMATION)

    logger.debug(
        '(%02d/%06d/%06d) Took %0.3fs to render tile (%s bytes), Source: %s, Timers: %s',
        tile.z,
        tile.x,
        tile.y,
        t.elapsed,
        len(data),
        headers.get('X-Imagery-Sources'),
        headers.get('X-Timers'), )

    write_to_mbtiles(tile, headers, data, output)


def write_to_mbtiles(tile, headers, data, output):
    try:
        with Timer() as t:
            outputter = output
            outputter.add_tile(tile, data)

        logger.debug(
            '(%02d/%06d/%06d) Took %0.3fs to write tile to mbtiles://%s',
            tile.z,
            tile.x,
            tile.y,
            t.elapsed,
            outputter._filename, )
    except Exception:
        logger.exception("Problem writing to mbtiles")


def queue_tile(tile, max_zoom, sources, output):
    queue_render(tile, sources, output)

    if tile.z < max_zoom:
        for child in mercantile.children(tile):
            queue_tile(child, max_zoom, sources, output)


def queue_render(tile, catalog, output):
    logger.debug('Enqueueing render for tile %s', tile)
    render_tile_exc_wrapper(tile, catalog, output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('x', type=int)
    parser.add_argument('y', type=int)
    parser.add_argument('zoom', type=int)
    parser.add_argument('max_zoom', type=int)
    parser.add_argument('mbtiles_prefix')

    args = parser.parse_args()
    root = Tile(args.x, args.y, args.zoom)

    logger.info('Caching sources for root tile %s to zoom %s', root,
                args.max_zoom)

    catalog = build_catalog(root, args.zoom, args.max_zoom)

    fname = '{}.mbtiles'.format(args.mbtiles_prefix)
    output = MbtilesOutput(fname)
    output.open()

    queue_tile(root, args.max_zoom, catalog, output)

    logger.info('Done processing root pyramid %s to zoom %s', root,
                args.max_zoom)

    output.close()
