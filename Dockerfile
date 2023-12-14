# WSGI service environment

FROM sourcepole/qwc-uwsgi-base:alpine-v2022.01.26

ADD requirements.txt /srv/qwc_service/requirements.txt

RUN pip3 install --no-cache-dir -r /srv/qwc_service/requirements.txt

ADD src /srv/qwc_service/
