#!/bin/bash

set -e

IFS=$'\n' WORKERS=($(kubectl get pod | grep worker | grep -v scaler | grep Running))

for WORKER in "${WORKERS[@]}"
do
    IFS=$' ' WORKER_NAME=($WORKER)
    printf "%s\n" "${WORKER_NAME}"
    kubectl logs -f pod/${WORKER_NAME} &
done

wait