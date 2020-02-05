FROM python:3.8.1-alpine3.11 as builder
     
COPY ./ /tmp/

WORKDIR /tmp/

RUN python setup.py build



FROM python:3.8.1-alpine3.11

COPY --from=builder /tmp/build/lib/pve_exporter /usr/local/bin/pve_exporter

COPY entrypoint.sh /

RUN chmod +x /entrypoint.sh

EXPOSE 9221

USER nobody

VOLUME /config

ENTRYPOINT [ "/entrypoint.sh" ]

CMD ["/usr/local/bin/pve_exporter", "/config/pve.yml", "9221" ]
