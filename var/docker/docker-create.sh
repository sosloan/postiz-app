#!/usr/bin/env bash

docker kill postiz || true 
docker rm postiz || true 
docker create --name postiz -p 3000:3000 -p 4200:4200 localhost/postiz

docker kill postiz-modal || true 
docker rm postiz-modal || true 
docker create --name postiz-modal -p 3000:3000 -p 4200:4200 localhost/postiz-modal

docker kill postiz-devlooper || true 
docker rm postiz-devlooper || true 
docker create --name postiz-devlooper -p 3000:3000 -p 4200:4200 localhost/postiz-devlooper
