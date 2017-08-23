# marblecutter-tilezen

This is a standalone (Python / Flask / WSGI) and Lambda-based dynamic tiler for
S3-hosted GeoTIFFs (digital elevation models and aerial imagery).

## Development

A `docker-compose.yml` has been provided to facilitate development. To start,
run:

```bash
docker-compose up
```

## Deployment

When not using Lambda, `marblecutter-tilezen` is best managed using Docker. To
build an image, run:

```bash
make server
```

To start it, run:

```bash
docker run --env-file .env -p 8000:8000 quay.io/mojodna/marblecutter-tilezen
```

## Lambda Deployment

Docker is required to create `deps/deps.tgz`, which contains binary dependencies
and Python packages built for the Lambda runtime.

### Up

[Up](https://github.com/apex/up) uses CloudFormation to deploy and manage Lambda
functions and API Gateway endpoints. It bundles a reverse proxy so that standard
web services can be deployed.

```bash
make deploy-up
```

### Apex

[Apex](https://github.com/apex/apex) manages Lambda functions using the AWS API.
For some purposes it may be preferable over using Up, such as when Lambda
implementation details (e.g. function timeouts) should not be glossed over.

```bash
make deploy-apex
```

### Gotchas

The IAM role assumed by Lambda (created by Up or Apex) must have the
[AmazonS3ReadOnlyAccess](https://console.aws.amazon.com/iam/home?region=us-east-1#policies/arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess)
policy attached to it and access from Mapzen's DEM source bucket granted to the
account being used in order for data to be read.
