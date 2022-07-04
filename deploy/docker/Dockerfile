FROM python:3.9.4-slim-buster as base

ARG DIR=/home/appuser
WORKDIR $DIR/app

RUN python -m venv $DIR/env
ENV PATH="$DIR/bin:$PATH"

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.txt

COPY src $DIR/app/src

RUN groupadd -g 999 appuser && \
  useradd -r -m -u 999 -g appuser -s /usr/sbin/nologin appuser

# Set restrictive permissions
RUN chmod -R 600 $DIR && \
  find $DIR -type d -exec chmod 700 '{}' \;

# Set ownership
RUN chown -R appuser:appuser $DIR


FROM base as rmq_pub

CMD runuser -u appuser -- "python" "src/rmq_pub.py"


FROM base as worker

CMD runuser -u appuser -- "python" "src/worker.py"


FROM base as worker_scaler

CMD runuser -u appuser -- "python" "src/worker_scaler.py"
