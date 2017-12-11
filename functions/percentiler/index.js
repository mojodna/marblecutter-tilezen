const { exec } = require("child_process");
const path = require("path");
const url = require("url");

const async = require("async");
const env = require("require-env");
const { Client } = require("pg");

const DATABASE_URL = env.require("DATABASE_URL");

const getPercentiles = (url, band, metaUrl, callback) =>
  exec(`/var/task/bin/percentiles.py ${url} ${band} ${metaUrl}`, (err, stdout, stderr) => {
    if (err) {
      return callback(err);
    }

    const [p2, p5, p95, p98] = stdout.split(/\s/).map(Number);

    return callback(null, {
      [band]: {
        min: p2,
        max: p98,
        p2,
        p5,
        p95,
        p98
      }
    });
  });

const getPercentilesForBands = (url, bands, callback) =>
  async.map(bands, (band, done) => {
    const bandUrl = url.replace(/{band}/, band);
    const metaUrl = url.replace(/s3:\/\/([^/]+)/, "https://$1.s3.amazonaws.com").replace(/B{band}.+/, "MTL.json");

    return getPercentiles(bandUrl, band, metaUrl, done);
  }, (err, percentiles) => {
    if (err) {
      return callback(err);
    }

    return callback(null, {
      values: percentiles.reduce((obj, x) => Object.assign(obj, x), {})
    });
  })


const updatePercentiles = (uri, bands, callback) => {
  return getPercentilesForBands(uri, bands, (err, percentiles) => {
    if (err) {
      return callback(err);
    }

    const client = new Client({
      connectionString: DATABASE_URL
    });

    return client.connect(err => {
      if (err) {
        return callback(err);
      }

      return client.query(
        "UPDATE imagery SET meta = meta || $1 WHERE url = $2",
        [
          JSON.stringify(percentiles),
          uri
        ],
        err => client.end(callback)
      );
    });
  });
};

exports.handle = (event, context, callback) => {
  const { Records: records } = event;

  return async.eachSeries(
    records,
    (record, done) => {
      switch (record.EventSource) {
        case "aws:sns":
          const {
            url: { Value: url }
          } = record.Sns.MessageAttributes;

          let { bands: { Value: bands } } = record.Sns.MessageAttributes;

          if (bands) {
            try {
              bands = JSON.parse(bands);
            } catch (err) {
              return done(err);
            }
          }

          return updatePercentiles(url, bands, done);

        default:
          return done(
            new Error("Unsupported event source: " + record.EventSource)
          );
      }
    },
    callback
  );
};
