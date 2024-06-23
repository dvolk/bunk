# BUNK

Run "Slurm" jobs on k8s

![BUNK title image with cute BUNK sloth hanging on a ship's wheel](bunk-title.png)

## Prerequisites

- `kind` (kubernetes in docker)
- `kubectl` (to manage kind)

## Setup

### Create image and cluster

```
docker build -t bunk:test .
kind create cluster --config kind.conf
kind load docker-image bunk:test
kubectl apply -f bunk-pods.yaml
```

## Running a job

Enter the bunk-login pod:

```
kubectl exec -it bunk-login /bin/bash
```

Run the example sbatch job:

```
cd /root/bunk
sbatch example.sbatch
```
