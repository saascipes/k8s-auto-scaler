#!/bin/bash

kubectl delete pod/worker-scaler --grace-period=0

helm delete k8s-auto-scaler-rabbitmq