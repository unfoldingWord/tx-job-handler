#!/usr/bin/env bash

# Environment variables DOCKER_USERNAME and DOCKER_PASSWORD must be set

# Parameter $1 is expected to be develop or master

echo "$DOCKER_PASSWORD" | docker login -u "$DOCKER_USERNAME" --password-stdin

if [ "$1" == "master" ]; then
    echo "Making MASTER branch image and pushing it" ;
    make imageMaster && make pushMasterImage
else
    echo "Making DEVELOP branch image and pushing it" ;
    make imageDev && make pushDevImage
fi
