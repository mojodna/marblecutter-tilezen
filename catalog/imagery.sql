CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE imagery (
    source text,
    filename character varying,
    url text,
    geom geometry(MultiPolygon, 4326),
    resolution double precision,
    approximate_zoom integer,
    min_zoom integer,
    max_zoom integer,
    priority integer DEFAULT 0,
    enabled boolean NOT NULL DEFAULT TRUE,
    meta jsonb,
    bands jsonb
);

-- when bands are tracked separately, this needs to change
ALTER TABLE imagery ADD CONSTRAINT unique_url UNIQUE (url);
CREATE INDEX imagery_geom_geom_idx ON imagery USING gist (geom);
