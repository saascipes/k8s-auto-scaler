#!/bin/bash

set -e

WORKERS=( $(kubectl get pod | grep worker | grep -v scaler) )

printf "%s\n" "${WORKERS[0][0]}"

kubectl logs -f pod/${WORKERS[0][0]}
