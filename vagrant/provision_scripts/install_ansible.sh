#!/bin/bash

# Minimal script to install ansible via apt as described:
# https://docs.ansible.com/ansible/latest/installation_guide/intro_installation.html#latest-releases-via-apt-ubuntu

# This will get the base boxes to a place where we can use the Vagrant Ansible Local
# Provisioner: https://www.vagrantup.com/docs/provisioning/ansible_local.html

# Do not pin ansible version, get latest from PyPy

sudo apt-add-repository ppa:ansible/ansible
sudo apt-get update
sudo apt-get install -y software-properties-common ansible
