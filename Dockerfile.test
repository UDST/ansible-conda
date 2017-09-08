FROM ubuntu

ENV DATA_DIRECTORY=/ansible-conda

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python \
        python-pip \
        python-apt \
        python-dev \
        build-essential \
        git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install setuptools wheel
RUN pip install ansible==2.3.2.0

ADD tests/integration/requirements.yml /tmp/requirements.yml
RUN ansible-galaxy install -r /tmp/requirements.yml

ADD tests/integration/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

VOLUME "${DATA_DIRECTORY}"
WORKDIR "${DATA_DIRECTORY}"

CMD "${DATA_DIRECTORY}/run-tests.sh"
