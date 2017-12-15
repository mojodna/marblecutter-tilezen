# coding=utf-8
import json
import logging
import traceback

import dateutil.parser

import pyspatialite.dbapi2 as spatialite
from marblecutter import get_zoom
from marblecutter.catalogs import WGS84_CRS, Catalog
from marblecutter.utils import Bounds, Source
from rasterio import warp

Infinity = float("inf")
LOG = logging.getLogger(__name__)


class MemoryCatalog(Catalog):
    def __init__(self):
        self._sources = []

    def add_source(self, geometry, attributes):
        self._sources.append((geometry, attributes))

    def get_sources(self, bounds, resolution):
        from shapely.geometry import box

        bounds, bounds_crs = bounds

        results = []
        zoom = get_zoom(max(resolution))
        ((left, right), (bottom, top)) = warp.transform(
            bounds_crs, WGS84_CRS, bounds[::2], bounds[1::2])
        bounds_geom = box(left, bottom, right, top)
        bounds_centroid = bounds_geom.centroid

        # Filter by zoom level and intersecting geometries
        for candidate in self._sources:
            (geom, attr) = candidate
            if attr['min_zoom'] <= zoom < attr['max_zoom'] and \
               geom.intersects(bounds_geom):
                results.append(candidate)

        # Sort by resolution and centroid distance
        results = sorted(
            results,
            key=lambda (geom, attr): (
                attr['priority'],
                int(attr['resolution']),
                bounds_centroid.distance(geom.centroid),
            )
        )

        # Remove duplicate URLs
        # From https://stackoverflow.com/a/480227
        seen = set()
        seen_add = seen.add
        results = [
            x for x in results
            if not (x[1]['url'] in seen or seen_add(x[1]['url']))
        ]

        # Pick only the attributes we care about
        results = [(a['url'], a['source'], a['resolution'])
                   for (_, a) in results]

        return results


class SpatialiteCatalog(Catalog):
    def __init__(self):
        self.conn = spatialite.connect(":memory:")

        cursor = self.conn.cursor()

        try:
            cursor.execute("SELECT InitSpatialMetadata()")

            cursor.execute("""
CREATE TABLE footprints (
    source text,
    filename character varying,
    url text,
    resolution double precision,
    min_zoom integer,
    max_zoom integer,
    priority double precision,
    meta text,
    recipes text,
    band_info text,
    acquired_at timestamp
)
            """)

            cursor.execute("""
SELECT AddGeometryColumn('footprints', 'geom', 4326, 'MULTIPOLYGON', 'XY')
            """)
            cursor.execute("SELECT CreateSpatialIndex('footprints', 'geom')")

            self.conn.commit()
        except Exception as e:
            LOG.warn(e)
            raise e
        finally:
            cursor.close()

    def add_source(self, source):
        cursor = self.conn.cursor()

        try:
            cursor.execute("""
INSERT INTO footprints (
    source,
    filename,
    url,
    resolution,
    min_zoom,
    max_zoom,
    priority,
    meta,
    recipes,
    band_info,
    acquired_at,
    geom
) VALUES (
    ?,
    ?,
    ?,
    ?,
    ?,
    ?,
    ?,
    ?,
    ?,
    ?,
    date(?),
    SetSRID(GeomFromGeoJSON(?), 4326)
)
            """, (source.name, source.filename, source.url, source.resolution,
                  source.min_zoom, source.max_zoom, source.priority,
                  json.dumps(source.meta), json.dumps(source.recipes),
                  json.dumps(source.band_info), None
                  if source.acquired_at is None else
                  dateutil.parser.parse(source.acquired_at).isoformat(),
                  json.dumps(source.geom)))

            self.conn.commit()
        except Exception as e:
            LOG.warn(e)
            raise e
        finally:
            cursor.close()

    def _candidates(self, bounds, resolution):
        cursor = self.conn.cursor()

        zoom = get_zoom(max(resolution))
        if bounds.crs == WGS84_CRS:
            left, bottom, right, top = bounds.bounds
        else:
            left, bottom, right, top = warp.transform_bounds(
                bounds.crs, WGS84_CRS, *bounds.bounds)

        left = left if left != Infinity else -180
        bottom = bottom if bottom != Infinity else -90
        right = right if right != Infinity else 180
        top = top if top != Infinity else 90

        try:
            cursor.execute("""
WITH bbox AS (
  SELECT SetSRID(
    GeomFromText('BOX({minx} {miny}, {maxx} {maxy})'),
    4326) geom
),
sources AS (
  SELECT
     url,
     source,
     resolution,
     coalesce(band_info, '{{}}') band_info,
     coalesce(meta, '{{}}') meta,
     coalesce(recipes, '{{}}') recipes,
     acquired_at,
     priority,
     ST_Multi(footprints.geom) geom,
     min_zoom,
     max_zoom
   FROM footprints
   JOIN bbox ON ST_Intersects(footprints.geom, bbox.geom)
   WHERE ? BETWEEN min_zoom AND max_zoom
)
SELECT
  url,
  source,
  resolution,
  band_info,
  meta,
  recipes,
  acquired_at,
  null band,
  priority
FROM sources
            """.format(minx=left, miny=bottom, maxx=right, maxy=top), (zoom, ))

            for record in cursor:
                yield Source(*record)
        except Exception as e:
            print(e)
            LOG.warn(e)
        finally:
            cursor.close()

    def get_sources(self, bounds, resolution):
        cursor = self.conn.cursor()

        zoom = get_zoom(max(resolution))
        if bounds.crs == WGS84_CRS:
            left, bottom, right, top = bounds.bounds
        else:
            left, bottom, right, top = warp.transform_bounds(
                bounds.crs, WGS84_CRS, *bounds.bounds)

        try:
            query = """
WITH bbox AS (
  SELECT SetSRID(GeomFromGeoJSON(?), 4326) geom
),
uncovered AS (
  SELECT SetSRID(GeomFromGeoJSON(?), 4327) geom
),
date_range AS (
  SELECT
    COALESCE(min(acquired_at), date('1970-01-01')) min,
    COALESCE(max(acquired_at), date('1970-01-01')) max
  FROM footprints
)
SELECT
  url,
  source,
  resolution,
  coalesce(band_info, '{{}}') band_info,
  coalesce(null, '{{}}') metas,
  -- coalesce(meta, '{{}}') metas,
  coalesce(recipes, '{{}}') recipes,
  acquired_at,
  null band, -- for Source constructor compatibility
  priority,
  ST_Area(ST_Intersection(uncovered.geom, footprints.geom)) /
    ST_Area(bbox.geom) coverage,
  AsGeoJSON(footprints.geom) geom,
  AsGeoJSON(ST_Difference(uncovered.geom, footprints.geom)) uncovered
FROM bbox, date_range, footprints
JOIN uncovered ON ST_Intersects(footprints.geom, uncovered.geom)
WHERE footprints.url NOT IN ({url_placeholders})
  AND ? BETWEEN min_zoom AND max_zoom
ORDER BY
  10 * coalesce(footprints.priority, 0.5) *
    .1 * (1 - (strftime('%s') -
               strftime('%s', COALESCE(acquired_at, date('2000-01-01')))) /
              (strftime('%s') - strftime('%s', date_range.min))) *
    50 *
      -- de-prioritize over-zoomed sources
      CASE WHEN ? / footprints.resolution >= 1
        THEN 1
        ELSE 1 / footprints.resolution
      END *
    ST_Area(
        ST_Intersection(bbox.geom, footprints.geom)) /
      ST_Area(bbox.geom) DESC
LIMIT 1
            """

            bbox = json.dumps({
                "type":
                "Polygon",
                "coordinates": [[[left, bottom], [left, top], [right, top],
                                 [right, bottom], [left, bottom]]]
            })

            uncovered = bbox
            urls = set()

            while True:
                url_placeholders = ", ".join("?" * len(urls))
                cursor.execute(
                    query.format(url_placeholders=url_placeholders),
                    (bbox, uncovered) + tuple(urls) + (zoom, min(resolution)))

                count = 0
                for record in cursor:
                    count += 1
                    yield Source(*record[:-1])

                    urls.add(record[0])
                    uncovered = record[-1]

                if count == 0:
                    break

        except Exception as e:
            LOG.warn(e)
            LOG.warn(traceback.format_exc(e))
        finally:
            cursor.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # curl http://localhost:8000/imagery/13-15/4393/2357.geojson > data.json
    with open("data.json") as f:
        features = json.load(f)

    cat = SpatialiteCatalog()
    for f in features["features"]:
        s = Source(geom=f["geometry"], **f["properties"])
        cat.add_source(s)

    # z14
    bounds = Bounds((13.0517578125, 60.46805012087461, 13.07373046875,
                     60.4788788301667), WGS84_CRS)
    # z13
    bounds = Bounds((13.0517578125, 60.45721779774396, 13.095703125,
                     60.4788788301667), WGS84_CRS)

    # 8/136/72
    bounds = Bounds((11.25, 60.930432202923335, 12.65625, 61.60639637138628),
                    WGS84_CRS)

    sources = list(cat.get_sources(bounds, (8, 8)))
    # print(sources)
