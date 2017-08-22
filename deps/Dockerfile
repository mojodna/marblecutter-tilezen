FROM lambci/lambda:build-python2.7

ARG http_proxy

# Install deps

RUN \
  rpm --rebuilddb && \
  yum install -y \
    automake16 \
    libcurl-devel \
    libpng-devel

# Fetch PROJ.4

RUN \
  curl -L http://download.osgeo.org/proj/proj-4.9.3.tar.gz | tar zxf - -C /tmp

# Build and install PROJ.4

WORKDIR /tmp/proj-4.9.3

RUN \
  ./configure \
    --prefix=/var/task && \
  make -j $(nproc) && \
  make install

# Fetch GDAL

RUN \
  mkdir -p /tmp/gdal && \
  curl -L http://download.osgeo.org/gdal/2.2.1/gdal-2.2.1.tar.gz | tar zxf - -C /tmp/gdal --strip-components=1

# Build + install GDAL

WORKDIR /tmp/gdal

RUN \
  ./configure \
    --prefix=/var/task \
    --datarootdir=/var/task/share/gdal \
    --with-jpeg=internal \
    --without-qhull \
    --without-mrf \
    --without-grib \
    --without-pcraster \
    --without-png \
    --without-gif \
    --without-pcidsk && \
  make -j $(nproc) && \
  make install

# add gdal-config to PATH so that rasterio can build

ENV PATH /var/task/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# Install Python deps

WORKDIR /var/task

COPY requirements.txt /var/task/requirements.txt

ENV PYTHONPATH /var/task/.pypath

RUN \
  mkdir -p .pypath && \
  pip install -U numpy Cython -t .pypath/ && \
  pip install -r requirements.txt -t .pypath/

RUN find . -name \*.so\* -exec strip {} \;

COPY deps/required.txt /var/task/required.txt
COPY deps/prune.sh /var/task/prune.sh

RUN /var/task/prune.sh
