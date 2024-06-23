# BUNK

Run "Slurm" jobs on kubernetes

![BUNK title image with cute BUNK sloth hanging on a ship's wheel](bunk-title.png)

## Prerequisites

- `kind` (kubernetes in docker)
- `kubectl` (to manage kind)

## Description

BUNK deploys a custom scaler and scheduler as kubernetes pods. The scaler monitors the scheduler and creates/deletes worker pods.

For users familiar with Slurm, BUNK includes Slurm-like binaries sbatch/squeue/scancel to control BUNK jobs.

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
