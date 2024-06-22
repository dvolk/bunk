# BUNK

![BUNK title image with cute BUNK sloth hanging on a ship's wheel](bunk-title.png)

Run "slurm" jobs on k8s

## Prerequisites

- kind (kubernetes in docker)
- kubectl (to manage kind)

## Setup

docker build -t bunk-login .
kind create cluster --config kind.conf
kind load docker-image bunk-login
kubectl apply -f bunk-login-pod.yaml

## Login node setup

...