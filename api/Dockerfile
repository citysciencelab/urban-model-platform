FROM python:3

RUN apt update && apt upgrade -y
RUN apt install -qq -y --no-install-recommends \
  libpq-dev gdal-bin libgdal-dev
RUN apt clean

#RUN useradd -ms /bin/bash python
#USER python

#RUN mkdir -p /home/python/workspace
#WORKDIR /home/python/workspace

WORKDIR /usr/src/app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt