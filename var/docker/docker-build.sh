#!/bin/bash

set -o xtrace

docker rmi localhost/postiz || true
docker build --target dist -t localhost/postiz -f Dockerfile.dev .
docker build --target devcontainer -t localhost/postiz-devcontainer -f Dockerfile.dev .

# Build backend
docker build --target dist -t localhost/postiz-backend -f Dockerfile.dev --build-arg TARGET=backend .

# Build frontend
docker build --target dist -t localhost/postiz-frontend -f Dockerfile.dev --build-arg TARGET=frontend .

# Build workers
docker build --target dist -t localhost/postiz-workers -f Dockerfile.dev --build-arg TARGET=workers .

# Build cron jobs
docker build --target dist -t localhost/postiz-cron -f Dockerfile.dev --build-arg TARGET=cron .
