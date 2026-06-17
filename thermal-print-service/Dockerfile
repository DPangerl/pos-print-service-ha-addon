ARG BUILD_FROM
FROM ${BUILD_FROM}

RUN apk add --no-cache \
    python3 \
    py3-pip \
    py3-requests \
    cups-client

COPY run.sh /
COPY print-todos.py /
COPY print_utils.py /
COPY web_server.py /

RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
