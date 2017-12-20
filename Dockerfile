FROM quay.io/mojodna/gdal:trunk
MAINTAINER Seth Fitzsimmons <seth@mojodna.net>

ARG http_proxy

ENV DEBIAN_FRONTEND noninteractive

RUN apt-get update \
  && apt-get upgrade -y \
  && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    cython3 \
    git \
    python3-dev \
    python3-pip \
    python3-wheel \
    python3-setuptools \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/marblecutter

COPY requirements-server.txt /opt/marblecutter/
COPY requirements.txt /opt/marblecutter/

RUN pip3 install -U pip numpy && \
  pip3 install -r requirements-server.txt && \
  rm -rf /root/.cache

COPY tilezen /opt/marblecutter/tilezen

USER nobody

ENV LC_ALL C.UTF-8
ENV GDAL_CACHEMAX 512
ENV GDAL_DISABLE_READDIR_ON_OPEN TRUE
ENV GDAL_HTTP_MERGE_CONSECUTIVE_RANGES YES
ENV VSI_CACHE TRUE
# tune this according to how much memory is available
ENV VSI_CACHE_SIZE 536870912
# override this accordingly; should be 2-4x $(nproc)
ENV WEB_CONCURRENCY 4

ENTRYPOINT ["gunicorn", "--reload", "-t", "300", "-k", "gevent", "-b", "0.0.0.0", "--access-logfile", "-", "tilezen.web:app"]
