#!/bin/bash

./bin/uninstall.sh

set -e

helm repo add bitnami https://charts.bitnami.com/bitnami

helm upgrade --install k8s-auto-scaler-rabbitmq bitnami/rabbitmq --wait --debug --values ./deploy/kubernetes/rabbitmq/values.yaml

cd deploy/kubernetes/helm
helm upgrade --install k8s-auto-scaler --debug --wait .