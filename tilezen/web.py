# coding=utf-8
from __future__ import absolute_import

import logging

from flask import jsonify, render_template, request, url_for
from marblecutter import footprints, tiling
from marblecutter.catalogs.postgis import PostGISCatalog
from marblecutter.formats.color_ramp import ColorRamp
from marblecutter.formats.geotiff import GeoTIFF
from marblecutter.formats.png import PNG
from marblecutter.transformations import Image
from marblecutter.web import app
from mercantile import Tile

from . import skadi
from .transformations import Hillshade, Normal, Terrarium

LOG = logging.getLogger(__name__)

ELEVATION_CATALOG = PostGISCatalog(table="dems")
GEOTIFF_FORMAT = GeoTIFF(area_or_point="Point")
HILLSHADE_GEOTIFF_FORMAT = GeoTIFF()
HILLSHADE_TRANSFORMATION = Hillshade(resample=True, add_slopeshade=True)
IMAGERY_CATALOG = PostGISCatalog(table="imagery")

CATALOGS = {
    "buffered_normal": ELEVATION_CATALOG,
    "hillshade": ELEVATION_CATALOG,
    "imagery": IMAGERY_CATALOG,
    "normal": ELEVATION_CATALOG,
    "terrarium": ELEVATION_CATALOG,
}
DATA_BAND_COUNTS = {"imagery": 3}
FORMATS = {
    "buffered_normal": PNG(),
    "hillshade": ColorRamp(),
    "imagery": PNG(),
    "normal": PNG(),
    "terrarium": PNG(),
}
RENDERERS = ["hillshade", "imagery", "buffered_normal", "normal", "terrarium"]
TRANSFORMATIONS = {
    "buffered_normal": Normal(collar=2),
    "hillshade": HILLSHADE_TRANSFORMATION,
    "imagery": Image(),
    "normal": Normal(),
    "terrarium": Terrarium(),
}

logging.getLogger("botocore.credentials").setLevel(logging.WARNING)


def make_prefix():
    host = request.headers.get("X-Forwarded-Host",
                               request.headers.get("Host", ""))

    # sniff for API Gateway
    if ".execute-api." in host and ".amazonaws.com" in host:
        return request.headers.get("X-Stage")


@app.route("/<renderer>/")
@app.route("/<prefix>/<renderer>/")
def meta(renderer, **kwargs):
    if renderer not in RENDERERS:
        return '', 404

    meta = {
        "minzoom": 0,
        "maxzoom": 22,
        "bounds": [-180, -85.05113, 180, 85.05113],
    }

    with app.app_context():
        meta["tiles"] = [
            "{}{{z}}/{{x}}/{{y}}.png".format(
                url_for(
                    "meta",
                    _external=True,
                    _scheme="",
                    prefix=make_prefix(),
                    renderer=renderer))
        ]

    return jsonify(meta)


@app.route("/<renderer>/preview")
@app.route("/<prefix>/<renderer>/preview")
def preview(renderer, **kwargs):
    if renderer not in RENDERERS:
        return '', 404

    with app.app_context():
        return render_template(
            "preview.html",
            tilejson_url=url_for(
                "meta",
                _external=True,
                _scheme="",
                prefix=make_prefix(),
                renderer=renderer))


@app.route("/geotiff/<int:z>/<int:x>/<int:y>.tif")
@app.route("/<prefix>/geotiff/<int:z>/<int:x>/<int:y>.tif")
def render_geotiff(z, x, y, **kwargs):
    tile = Tile(x, y, z)

    headers, data = tiling.render_tile(
        tile,
        ELEVATION_CATALOG,
        format=GEOTIFF_FORMAT,
        scale=2,
        data_band_count=1)

    return data, 200, headers


@app.route("/<renderer>/<int:z>/<int:x>/<int:y>.png")
@app.route("/<renderer>/<int:z>/<int:x>/<int:y>@<int:scale>x.png")
@app.route("/<prefix>/<renderer>/<int:z>/<int:x>/<int:y>.png")
@app.route("/<prefix>/<renderer>/<int:z>/<int:x>/<int:y>@<int:scale>x.png")
def render_png(renderer, z, x, y, scale=1, **kwargs):
    tile = Tile(x, y, z)

    headers, data = tiling.render_tile(
        tile,
        CATALOGS[renderer],
        format=FORMATS[renderer],
        transformation=TRANSFORMATIONS.get(renderer),
        scale=scale,
        data_band_count=DATA_BAND_COUNTS.get(renderer, 1))

    return data, 200, headers


@app.route("/<renderer>/<int:z>/<int:x>/<int:y>.geojson")
@app.route("/<renderer>/<int:z>/<int:x>/<int:y>@<int:scale>x.geojson")
@app.route("/<prefix>/<renderer>/<int:z>/<int:x>/<int:y>.geojson")
@app.route("/<prefix>/<renderer>/<int:z>/<int:x>/<int:y>@<int:scale>x.geojson")
def render_geojson(renderer, z, x, y, scale=1, **kwargs):
    tile = Tile(x, y, z)

    data = {
        "type": "FeatureCollection",
        "features": [],
    }
    headers = {"Content-Type": "application/json"}

    [
        data["features"].append(footprint)
        for footprint in footprints.features_for_tile(
            tile, CATALOGS[renderer], scale=scale)
    ]

    return jsonify(data), 200, headers


@app.route("/<renderer>/<int:z>/<int:x>/<int:y>.json")
@app.route("/<renderer>/<int:z>/<int:x>/<int:y>@<int:scale>x.json")
@app.route("/<prefix>/<renderer>/<int:z>/<int:x>/<int:y>.json")
@app.route("/<prefix>/<renderer>/<int:z>/<int:x>/<int:y>@<int:scale>x.json")
def render_json(renderer, z, x, y, scale=1, **kwargs):
    tile = Tile(x, y, z)

    headers = {"Content-Type": "application/json"}

    data = list(
        footprints.sources_for_tile(tile, CATALOGS[renderer], scale=scale))

    return jsonify(data), 200, headers


@app.route("/hillshade/<int:z>/<int:x>/<int:y>.tif")
@app.route("/<prefix>/hillshade/<int:z>/<int:x>/<int:y>.tif")
def render_hillshade_tiff(z, x, y, **kwargs):
    tile = Tile(x, y, z)

    headers, data = tiling.render_tile(
        tile,
        CATALOGS['hillshade'],
        format=HILLSHADE_GEOTIFF_FORMAT,
        transformation=HILLSHADE_TRANSFORMATION,
        scale=2,
        data_band_count=1)

    return data, 200, headers


@app.route("/skadi/<_>/<tile>.hgt.gz")
@app.route("/<prefix>/skadi/<_>/<tile>.hgt.gz")
def render_skadi(_, tile, **kwargs):
    headers, data = skadi.render_tile(tile)

    return data, 200, headers
