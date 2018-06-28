#!/bin/bash

python3 -b -m pytest --showlocals --junitxml /vagrant/shellresults.xml -s -v ./tests
