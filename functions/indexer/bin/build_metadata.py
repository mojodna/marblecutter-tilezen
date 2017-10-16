#!/usr/bin/env python
# coding=utf-8
from __future__ import print_function

import argparse
import json
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--meta', nargs='*')
    args = parser.parse_args()

    incoming = json.load(sys.stdin)

    geojson = {
        "type": "Feature",
        "properties": {},
        "geometry": {
            "type": "MultiPolygon",
            "coordinates": [],
        }
    }

    if args.meta:
        for a in args.meta:
            k, v = a.split('=', 1)
            if v:
                geojson['properties'][k] = json.loads(v)

    assert incoming['type'] == 'FeatureCollection', \
        "Expecting a FeatureCollection GeoJSON object"

    for feature in incoming['features']:
        assert feature['type'] == 'Feature'

        geometry = feature['geometry']
        assert geometry['type'] in ('Polygon', 'MultiPolygon'), \
            "Expecting Polygon or MultiPolygon features"

        if geometry['type'] == 'Polygon':
            geojson['geometry']['coordinates'].append(
                geometry['coordinates']
            )
        elif geometry['type'] == 'MultiPolygon':
            geojson['geometry']['coordinates'].extend(
                geometry['coordinates']
            )

    json.dump(geojson, sys.stdout)


if __name__ == '__main__':
    main()
