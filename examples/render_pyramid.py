# noqa
# coding=utf-8
from __future__ import print_function

import argparse
import hashlib
import logging
import os
import random
import time
from functools import wraps
from multiprocessing.dummy import Pool

from shapely import wkb
from shapely.geometry import box

import boto3
import botocore
import mercantile
import psycopg2
import psycopg2.extras
import threading
from marblecutter import tiling
from marblecutter.formats import PNG, GeoTIFF
from marblecutter.sources import MemoryAdapter
from marblecutter.stats import Timer
from marblecutter.transformations import Normal, Terrarium
from mercantile import Tile

logging.basicConfig(level=logging.INFO)
# Quieting boto messages down a little
logging.getLogger('boto3.resources.action').setLevel(logging.WARNING)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('marblecutter').setLevel(logging.WARNING)
logging.getLogger('marblecutter.mosaic').setLevel(logging.WARNING)
logging.getLogger('marblecutter.sources').setLevel(logging.WARNING)
logger = logging.getLogger('batchtiler')

if os.environ.get('VERBOSE'):
    logger.setLevel(logging.DEBUG)


THREAD_LOCAL = threading.local()


def initialize_thread():
    # Each thread needs its own boto3 Session object - it's not threadsafe
    THREAD_LOCAL.session = boto3.session.Session()
    THREAD_LOCAL.s3 = THREAD_LOCAL.session.resource('s3')


POOL_SIZE = 12
POOL = Pool(POOL_SIZE, initializer=initialize_thread)
OVERWRITE = os.environ.get('OVERWRITE_EXISTING_OBJECTS') == 'true'
# Only render these tile types
ONLY_RENDER = os.environ.get('ONLY_RENDER').split(',') \
              if os.environ.get('ONLY_RENDER') else None

GEOTIFF_FORMAT = GeoTIFF()
PNG_FORMAT = PNG()
NORMAL_TRANSFORMATION = Normal()
TERRARIUM_TRANSFORMATION = Terrarium()

RENDER_COMBINATIONS = [
    ("normal", NORMAL_TRANSFORMATION, PNG_FORMAT, ".png", 1),
    ("terrarium", TERRARIUM_TRANSFORMATION, PNG_FORMAT, ".png", 1),
    ("geotiff", None, GEOTIFF_FORMAT, ".tif", 2),
]


def s3_key(key_prefix, tile_type, tile, key_suffix):
    key = '{}/{}/{}/{}{}'.format(
        tile_type,
        tile.z,
        tile.x,
        tile.y,
        key_suffix,
    )

    h = hashlib.md5(key).hexdigest()[:6]
    key = '{}/{}'.format(
        h,
        key,
    )

    if key_prefix:
        key = '{}/{}'.format(key_prefix, key)

    return key


def write_to_s3(obj,
                tile,
                tile_type,
                data,
                key_suffix,
                headers):

    tries = 0
    wait = 1.0
    while True:
        try:
            obj.put(
                Body=data,
                ContentType=headers['Content-Type'],
                Metadata={k: headers[k]
                          for k in headers if k != 'Content-Type'})

            logger.debug(
                "Saved tile %s to s3://%s/%s at try %s",
                tile, obj.bucket_name, obj.key, tries,
            )

            return obj
        except botocore.exceptions.ClientError as e:
            if e.response.get('Error', {}).get('Code') == 'SlowDown':
                logger.info(
                    "SlowDown received, try %s, while saving "
                    "%s to s3://%s/%s, waiting %0.1f sec",
                    tries, tile, obj.bucket_name, obj.key, wait,
                )
                time.sleep(wait)
                wait = min(30.0, wait * 2.0)
            else:
                raise


def build_source_index(tile, min_zoom, max_zoom):
    source_cache = MemoryAdapter()
    bbox = box(*mercantile.bounds(tile))

    database_url = os.environ.get('DATABASE_URL')

    with psycopg2.connect(database_url) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT
                    filename, resolution, source, url,
                    min_zoom, max_zoom, priority, approximate_zoom,
                    wkb_geometry
                FROM
                    footprints
                WHERE
                    ST_Intersects(
                        wkb_geometry,
                        ST_GeomFromText(%s, 4326)
                    )
                    AND numrange(min_zoom, max_zoom) && numrange(%s, %s)
                    AND enabled = true
                """, (bbox.to_wkt(), min_zoom, max_zoom))

            logger.info("Found %s sources for tile %s, zoom %s-%s",
                cur.rowcount, tile, min_zoom, max_zoom)

            if not cur.rowcount:
                raise ValueError("No sources found for this tile")

            for row in cur:
                row = dict(row)
                shape = wkb.loads(row.pop('wkb_geometry').decode('hex'))
                source_cache.add_source(shape, row)

    return source_cache


def render_tile_exc_wrapper(tile, s3_details, sources):
    try:
        render_tile_and_put_to_s3(tile, s3_details, sources)
    except Exception:
        logger.exception('Error while processing tile %s', tile)
        raise


def s3_obj_exists(obj):
    wait = 0.0

    while True:
        time.sleep(wait)

        try:
            obj.load()
            return True
        except botocore.exceptions.ClientError, e:
            error_code = int(e.response['Error']['Code'])
            if error_code == 404:
                return False
            else:
                wait = min(30.0, wait * 2.0) if wait > 0 else 1.0
                wait += random.uniform(0.0, wait / 2.0)


def render_tile_and_put_to_s3(tile, s3_details, sources):
    s3_bucket, s3_key_prefix = s3_details

    for (type, transformation, format, ext, scale) in RENDER_COMBINATIONS:
        if ONLY_RENDER and type not in ONLY_RENDER:
            logger.debug(
                '(%02d/%06d/%06d) Skipping render because '
                'type %s not in %s',
                tile.z, tile.x, tile.y,
                type, ONLY_RENDER,
            )
            continue

        key = s3_key(s3_key_prefix, type, tile, ext)
        obj = THREAD_LOCAL.s3.Object(s3_bucket, key)
        if not OVERWRITE and s3_obj_exists(obj):
            logger.debug(
                '(%02d/%06d/%06d) Skipping existing %s tile',
                tile.z, tile.x, tile.y, type,
            )
            continue

        with Timer() as t:
            (headers, data) = tiling.render_tile(
                tile, sources,
                format=format,
                transformation=transformation,
                scale=scale)

        logger.debug(
            '(%02d/%06d/%06d) Took %0.3fs to render %s tile (%s bytes), Source: %s, Timers: %s',
            tile.z, tile.x, tile.y, t.elapsed, type,
            len(data),
            headers.get('X-Imagery-Sources'),
            headers.get('X-Timers'),
        )

        with Timer() as t:
            obj = write_to_s3(obj, tile, type, data, ext, headers)

        logger.debug(
            '(%02d/%06d/%06d) Took %0.3fs to write %s tile to s3://%s/%s',
            tile.z, tile.x, tile.y, t.elapsed, type,
            obj.bucket_name, obj.key,
        )


def queue_tile(tile, max_zoom, s3_details, sources):
    queue_render(tile, s3_details, sources)

    if tile.z < max_zoom:
        for child in mercantile.children(tile):
            queue_tile(child, max_zoom, s3_details, sources)


def queue_render(tile, s3_details, sources):
    logger.debug('Enqueueing render for tile %s', tile)
    POOL.apply_async(render_tile_exc_wrapper, args=[tile, s3_details, sources])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('x', type=int)
    parser.add_argument('y', type=int)
    parser.add_argument('zoom', type=int)
    parser.add_argument('max_zoom', type=int)
    parser.add_argument('bucket')
    parser.add_argument('--key_prefix')

    args = parser.parse_args()
    root = Tile(args.x, args.y, args.zoom)

    logger.info('Caching sources for root tile %s to zoom %s',
                root, args.max_zoom)

    source_index = build_source_index(root, args.zoom, args.max_zoom)

    logger.info('Running %s processes', POOL_SIZE)

    queue_tile(root, args.max_zoom, (args.bucket, args.key_prefix),
               source_index)

    POOL.close()
    POOL.join()
    logger.info('Done processing root pyramid %s to zoom %s',
                root, args.max_zoom)
