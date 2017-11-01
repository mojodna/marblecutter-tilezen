import logging

from rasterio import warp

from marblecutter import get_zoom
from marblecutter.catalogs import WGS84_CRS, Catalog

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
