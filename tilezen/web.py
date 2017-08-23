# coding=utf-8
from __future__ import absolute_import

import logging

from cachetools.func import lru_cache
from flask import jsonify, render_template, request, url_for
from mercantile import Tile

from marblecutter import tiling
from marblecutter.catalogs import PostGISCatalog
from marblecutter.formats import PNG, ColorRamp, GeoTIFF
from marblecutter.web import app

from . import skadi
from .transformations import Hillshade, Normal, Terrarium

LOG = logging.getLogger(__name__)

GEOTIFF_FORMAT = GeoTIFF()
HILLSHADE_TRANSFORMATION = Hillshade(resample=True, add_slopeshade=True)

FORMATS = {
    "buffered_normal": PNG(),
    "hillshade": ColorRamp(),
    "normal": PNG(),
    "terrarium": PNG(),
}
RENDERERS = ["hillshade", "buffered_normal", "normal", "terrarium"]
TRANSFORMATIONS = {
    "buffered_normal": Normal(collar=2),
    "hillshade": HILLSHADE_TRANSFORMATION,
    "normal": Normal(),
    "terrarium": Terrarium(),
}


@lru_cache()
def catalog():
    return PostGISCatalog()


@app.route("/<prefix>/<renderer>/")
@app.route("/<renderer>/")
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
                    prefix=request.headers.get("X-Stage"),
                    renderer=renderer))
        ]

    return jsonify(meta)


@app.route("/<prefix>/<renderer>/preview")
@app.route("/<renderer>/preview")
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
                prefix=request.headers.get("X-Stage"),
                renderer=renderer))


@app.route("/<prefix>/geotiff/<int:z>/<int:x>/<int:y>.tif")
@app.route("/geotiff/<int:z>/<int:x>/<int:y>.tif")
def render_geotiff(z, x, y, **kwargs):
    tile = Tile(x, y, z)

    headers, data = tiling.render_tile(
        tile, catalog(), format=GEOTIFF_FORMAT, scale=2)

    return data, 200, headers


@app.route("/<prefix>/<renderer>/<int:z>/<int:x>/<int:y>.png")
@app.route("/<renderer>hillshade/<int:z>/<int:x>/<int:y>.png")
@app.route("/<prefix>/<renderer>/<int:z>/<int:x>/<int:y>@<int:scale>x.png")
@app.route("/<renderer>/<int:z>/<int:x>/<int:y>@<int:scale>x.png")
def render_png(renderer, z, x, y, scale=1, **kwargs):
    tile = Tile(x, y, z)

    headers, data = tiling.render_tile(
        tile,
        catalog(),
        format=FORMATS[renderer],
        transformation=TRANSFORMATIONS.get(renderer),
        scale=scale)

    return data, 200, headers


@app.route("/<prefix>/hillshade/<int:z>/<int:x>/<int:y>.tif")
@app.route("/hillshade/<int:z>/<int:x>/<int:y>.tif")
def render_hillshade_tiff(z, x, y, **kwargs):
    tile = Tile(x, y, z)

    headers, data = tiling.render_tile(
        tile,
        catalog(),
        format=GEOTIFF_FORMAT,
        transformation=HILLSHADE_TRANSFORMATION,
        scale=2)

    return data, 200, headers


@app.route("/<prefix>/skadi/<_>/<tile>.hgt.gz")
@app.route("/skadi/<_>/<tile>.hgt.gz")
def render_skadi(_, tile, **kwargs):
    headers, data = skadi.render_tile(tile)

    return data, 200, headers
