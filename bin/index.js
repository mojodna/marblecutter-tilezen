#!/usr/bin/env node
const AWS = require("aws-sdk");

const sns = new AWS.SNS();

const [source, url, meta] = process.argv.slice(2);

console.log("source:", source);
console.log("url:", url);

if (source == null || url == null) {
  console.warn("Usage: index <source> <url>");
  process.exit(1);
}

sns.publish({
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
      StringValue: meta || JSON.stringify({})
    }
  },
  // TODO env
  TopicArn: "arn:aws:sns:us-east-1:221726267240:tilezen-indexer"
}, (err, data) => {
  if (err) {
    throw err;
  }

  console.log(data);
})
