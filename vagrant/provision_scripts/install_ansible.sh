#!/bin/bash

# Installs Ansible via pip so that we can pin a specific version

# This will get the base boxes to a place where we can use the Vagrant Ansible Local
# Provisioner: https://www.vagrantup.com/docs/provisioning/ansible_local.html

sudo apt-get update
sudo apt-get install -y python3-pip
sudo pip3 install ansible~=2.7.0
