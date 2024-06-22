# BUNK

Run "Slurm" jobs on k8s

![BUNK title image with cute BUNK sloth hanging on a ship's wheel](bunk-title.png)

## Prerequisites

- `kind` (kubernetes in docker)
- `kubectl` (to manage kind)

## Setup

```
docker build -t bunk .
kind create cluster --config kind.conf
kind load docker-image bunk
kubectl apply -f bunk-pods.yaml
```

## Scaler setup

- copy `~/.kube/config` to the `bunk-scaler` pod in `/root/.kube/config`

## Demo

Enter the bunk-login pod:

```
kubectl exec -it bunk-login /bin/bash
```

Run the example sbatch job:

```
cd /root/bunk
sbatch example.sbatch
```
