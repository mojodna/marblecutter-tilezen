#!/usr/bin/env node
const AWS = require("aws-sdk");

const sns = new AWS.SNS();

const [url, bandsOpt] = process.argv.slice(2);

if (url == null || bandsOpt == null) {
  console.warn("Usage: index <url> <bands>");
  process.exit(1);
}

const bands = bandsOpt.split(/\s/).map(Number);

sns.publish({
  Message: [url, bands].join(": "),
  MessageAttributes: {
    url: {
      DataType: "String",
      StringValue: url
    },
    bands: {
      DataType: "String",
      StringValue: JSON.stringify(bands)
    }
  },
  // TODO env
  TopicArn: "arn:aws:sns:us-east-1:221726267240:tilezen-percentiler"
}, (err, data) => {
  if (err) {
    throw err;
  }

  console.log(url);
})
