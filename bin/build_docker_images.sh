#!/bin/bash

set -e

export DOCKER_BUILDKIT=1

docker buildx build -t worker:v0.0.1 --target worker --load -f deploy/docker/Dockerfile .

docker buildx build -t worker_scaler:v0.0.1 --target worker_scaler --load -f deploy/docker/Dockerfile .

docker buildx build -t rmq_pub:v0.0.1 --target rmq_pub --load -f deploy/docker/Dockerfile .