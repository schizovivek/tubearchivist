# build the tube archivist image from default python slim image

FROM python:3.10.2-slim-bullseye
ARG TARGETPLATFORM

ENV PYTHONUNBUFFERED 1

# install distro packages needed
RUN apt-get clean && apt-get -y update && apt-get -y install --no-install-recommends \
    build-essential \
    nginx \
    atomicparsley \
    curl && rm -rf /var/lib/apt/lists/*

# get newest patched ffmpeg and ffprobe builds for amd64 fall back to repo ffmpeg for arm64
RUN if [ "$TARGETPLATFORM" = "linux/amd64" ] ; then \
    curl -s https://api.github.com/repos/yt-dlp/FFmpeg-Builds/releases/latest \
        | grep browser_download_url \
        | grep linux64-gpl-4.4.tar.xz \
        | cut -d '"' -f 4 \
        | xargs curl -L --output ffmpeg.tar.xz && \
        tar -xf ffmpeg.tar.xz --strip-components=2 --no-anchored -C /usr/bin/ "ffmpeg" && \
        tar -xf ffmpeg.tar.xz --strip-components=2 --no-anchored -C /usr/bin/ "ffprobe" && \
        rm ffmpeg.tar.xz \
    ; elif [ "$TARGETPLATFORM" = "linux/arm64" ] ; then \
        apt-get -y update && apt-get -y install --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/* \
    ; fi

# make folders
RUN mkdir /cache
RUN mkdir /youtube
RUN mkdir /app

# install python dependencies
COPY ./tubearchivist/requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r requirements.txt --src /usr/local/src

# copy config files
COPY docker_assets/nginx.conf /etc/nginx/conf.d/

# copy application into container
COPY ./tubearchivist /app
COPY ./docker_assets/run.sh /app
COPY ./docker_assets/uwsgi.ini /app

# volumes
VOLUME /cache
VOLUME /youtube

# start
WORKDIR /app
EXPOSE 8000

RUN chmod +x ./run.sh

CMD ["./run.sh"]
