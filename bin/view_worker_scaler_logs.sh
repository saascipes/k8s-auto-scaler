#!/bin/bash

set -e

WORKER_SCALER=( $(kubectl get pod | grep worker-scaler) )

printf "%s\n" "${WORKER_SCALER[0]}"

kubectl logs -f pod/${WORKER_SCALER[0]}
