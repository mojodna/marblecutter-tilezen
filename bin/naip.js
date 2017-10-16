#!/usr/bin/env node
const assert = require("assert");
const path = require("path");
const url = require("url");

const async = require("async");
const AWS = require("aws-sdk");
const shapefile = require("shapefile");

const s3 = new AWS.S3();
const sns = new AWS.SNS();

const [uri] = process.argv.slice(2);

// s3://aws-naip/al/2013/1m/shpfl/naip_3_13_2_1_al.dbf
if (uri == null) {
  console.error("Usage: naip <dbf>");
  process.exit(1);
}

const index = (source, url, meta, callback) =>
  sns.publish(
    {
      Message: [source, url].join(": "),
      MessageAttributes: {
        source: {
          DataType: "String",
          StringValue: source
        },
        url: {
          DataType: "String",
          StringValue: url
        },
        meta: {
          DataType: "String",
          StringValue: meta ? JSON.stringify(meta) : JSON.stringify({})
        }
      },
      // TODO env
      TopicArn: "arn:aws:sns:us-east-1:221726267240:tilezen-indexer"
    },
    (err, data) => {
      if (err) {
        console.warn(err)
      }
      
      return callback(err, data);
    }
  );

const queue = async.queue(({ name, source, uri, meta }, done) => {
  const { host: Bucket, pathname } = url.parse(uri);

  return s3.headObject(
    {
      Bucket,
      Key: pathname.slice(1),
      RequestPayer: "requester"
    },
    (err, data) => {
      console.log(name);

      if (err) {
        console.warn(err.code, uri);
        return done(err);
      }

      return index(source, uri, meta, done);
    }
  );
}, 64);

const { host: Bucket, pathname } = url.parse(uri);
const dir = path.resolve(path.dirname(pathname), "..");
const [state, year] = dir.split("/").slice(1,3);

s3.getObject(
  {
    Bucket,
    Key: pathname.slice(1),
    RequestPayer: "requester"
  },
  (err, data) => {
    if (err) {
      throw err;
    }

    const { Body: dbf } = data;

    shapefile.openDbf(dbf).then(source =>
      source.read().then(function repeat(result) {
        if (result.done) {
          return;
        }

        // TODO attempt to detect schemas
        switch (true) {
          case ["mi"].includes(state) && year === "2012": {
            const {
              value: meta,
              value: {
                quads375_Q: name,
                USGSID: quadrangle,
                Qdrnt: quadrant,
                Res: resolution,
                UTM: utmZone,
                SrcImgDate: srcImgDate
              }
            } = result;

            try {
              assert(name, "name");
              assert(quadrangle, "quadrangle");
              assert(quadrant, "quadrant");
              assert(resolution, "resolution");
              assert(utmZone, "utmZone");
              assert(srcImgDate, "srcImgDate");
            } catch (err) {
              console.log(err.message);
              console.log(result.value);
              process.exit(1);
            }

            const filename = `m_${quadrangle}_${quadrant.toLowerCase()}_${utmZone}_${resolution}_${srcImgDate}.tif`;
            const uri = `s3://${Bucket}${path.join(
              dir,
              "rgb",
              quadrangle.slice(0, 5),
              filename
            )}`;

            queue.push({
              name,
              source: `NAIP - ${state.toUpperCase()} - ${year}`,
              uri,
              meta
            });
            break;
          }

          case !["al", "de", "fl", "ga", "la", "nv"].includes(state) && year === "2013": {
            let {
              value: meta,
              value: {
                quads375_Q: name,
                naip_3_132: quadrangle,
                naip_3_133: quadrant,
                naip_3_135: resolution,
                naip_3_134: utmZone,
                naip_3_136: srcImgDate
              }
            } = result;

            resolution = resolution == null ? "h" : resolution;

            try {
              assert(name, "name");
              assert(quadrangle, "quadrangle");
              assert(quadrant, "quadrant");
              assert(resolution, "resolution");
              assert(utmZone, "utmZone");
              assert(srcImgDate, "srcImgDate");
            } catch (err) {
              console.log(err.message);
              console.log(result.value);
              process.exit(1);
            }

            const filename = `m_${quadrangle}_${quadrant.toLowerCase()}_${utmZone}_${resolution}_${srcImgDate}.tif`;
            const uri = `s3://${Bucket}${path.join(
              dir,
              "rgb",
              quadrangle.slice(0, 5),
              filename
            )}`;

            queue.push({
              name,
              source: `NAIP - ${state.toUpperCase()} - ${year}`,
              uri,
              meta
            });
            break;
          }

          default: {
            let {
              value: meta,
              value: {
                QQNAME: name,
                APFONAME: quadrangle,
                QUADRANT: quadrant,
                Res: resolution,
                UTM: utmZone,
                SrcImgDate: srcImgDate
              }
            } = result;

            resolution = resolution === 0 ? "h" : resolution;

            try {
              assert(name, "name");
              assert(quadrangle, "quadrangle");
              assert(quadrant, "quadrant");
              assert(resolution, "resolution");
              assert(utmZone, "utmZone");
              assert(srcImgDate, "srcImgDate");
            } catch (err) {
              console.log(err.message);
              console.warn(result.value);
              process.exit(1);
            }

            const filename = `m_${quadrangle}_${quadrant.toLowerCase()}_${utmZone}_${resolution}_${srcImgDate}.tif`;
            const uri = `s3://${Bucket}${path.join(
              dir,
              "rgb",
              quadrangle.slice(0, 5),
              filename
            )}`;

            queue.push({
              name,
              source: `NAIP - ${state.toUpperCase()} - ${year}`,
              uri,
              meta
            });
            break;
          }
        }

        return source.read().then(repeat);
      })
    );
  }
);
