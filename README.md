# BUNK

Run "Slurm" jobs on k8s

![BUNK title image with cute BUNK sloth hanging on a ship's wheel](bunk-title.png)

## Prerequisites

- kind (kubernetes in docker)
- kubectl (to manage kind)

## Setup

```
docker build -t bunk-login:v1 .
kind create cluster --config kind.conf
kind load docker-image bunk-login:v1
kubectl apply -f bunk-login-pod.yaml
```

## Login node setup

```
...
```
