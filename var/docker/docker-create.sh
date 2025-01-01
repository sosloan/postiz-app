#!/usr/bin/env bash

docker kill postiz-backend || true 
docker rm postiz-backend || true 
docker create --name postiz-backend -p 3000:3000 localhost/postiz-backend

docker kill postiz-frontend || true 
docker rm postiz-frontend || true 
docker create --name postiz-frontend -p 4200:4200 localhost/postiz-frontend

docker kill postiz-workers || true 
docker rm postiz-workers || true 
docker create --name postiz-workers localhost/postiz-workers

docker kill postiz-cron || true 
docker rm postiz-cron || true 
docker create --name postiz-cron localhost/postiz-cron
