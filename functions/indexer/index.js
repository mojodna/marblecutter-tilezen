const { exec } = require("child_process");
const path = require("path");
const url = require("url");

const async = require("async");
const env = require("require-env");
const { Client } = require("pg");

const getInfo = (url, callback) =>
  exec(`/var/task/bin/get_info.sh ${url}`, (err, stdout, stderr) => {
    if (err) {
      return callback(err);
    }

    try {
      return callback(null, JSON.parse(stdout));
    } catch (err) {
      return callback(err);
    }
  });

const indexSource = (source, uri, meta, callback) =>
  getInfo(uri, (err, info) => {
    if (err) {
      return callback(err);
    }

    const client = new Client({
      connectionString: env.require("DATABASE_URL")
    });

    return client.connect(err => {
      if (err) {
        return callback(err);
      }

      const filename = path.basename(url.parse(uri).path);
      const {
        geometry,
        properties: { resolution_in_meters: resolution }
      } = info;
      const properties = Object.assign(meta, info.properties);
      const approximateZoom = Math.ceil(
        Math.log2(2 * Math.PI * 6371837 / (resolution * 256))
      );
      const minZoom = Math.max(0, approximateZoom - 5);
      const maxZoom = approximateZoom + 2;

      // TODO recipes
      return client.query(
        "INSERT INTO imagery (source, filename, url, geom, resolution, meta, approximate_zoom, min_zoom, max_zoom) VALUES ($1, $2, $3, ST_SetSRID(ST_GeomFromGeoJSON($4), 4326), $5, $6, $7, $8, $9)",
        [
          source,
          filename,
          uri,
          geometry,
          resolution,
          properties,
          approximateZoom,
          minZoom,
          maxZoom
        ],
        err => client.end(callback)
      );
    });
  });

exports.handle = (event, context, callback) => {
  const { Records: records } = event;

  return async.eachSeries(
    records,
    (record, done) => {
      switch (record.EventSource) {
        case "aws:sns":
          const {
            source: { Value: source },
            url: { Value: url }
          } = record.Sns.MessageAttributes;

          let {
            meta: { Value: meta }
          } = record.Sns.MessageAttributes;

          if (meta) {
            try {
              meta = JSON.parse(meta);
            } catch (err) {
              return done(err);
            }
          }

          return indexSource(source, url, meta, done);

        default:
          return done(
            new Error("Unsupported event source: " + record.EventSource)
          );
      }
    },
    callback
  );
};
