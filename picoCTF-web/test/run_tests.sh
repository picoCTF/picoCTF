#!/bin/bash
# [TODO] - remove /vagrant and update directories

test_path="./unit_tests"
output_results_prefix="unit"

python3 -b -m pytest --showlocals --junitxml /vagrant/${output_results_prefix}results.xml -s -v "$test_path"


test_path="./functional_tests"
output_results_prefix="functional"

python3 -b -m pytest --showlocals --junitxml /vagrant/${output_results_prefix}results.xml -s -v "$test_path"
