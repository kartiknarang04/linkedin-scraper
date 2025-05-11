#!/usr/bin/env bash

# Update & install dependencies
apt-get update
apt-get install -y wget unzip curl gnupg

# Install Chrome
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
apt install -y ./google-chrome-stable_current_amd64.deb
