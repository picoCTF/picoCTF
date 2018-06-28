#!/usr/bin/env python3

# Simple script to programmaticly load problems from a shell server
# If using a custom APP_SETTINGS_FILE, ensure the appropriate
# environment variable is set prior to running this script. This script is best
# run from the pico-web role (ansible/roles/pico-web/tasks/main.yml)

import sys

# The picoCTF API
import api


def main(name):

    try:
        # If a server by this name exists we can load problems
        shell_server = api.shell_servers.get_server(name=name)
        try:
            # Load problems and bundles from the shell server
            api.shell_servers.load_problems_from_server(shell_server["sid"])

            # Set problems to disabled
            for p in api.problem.get_all_problems(show_disabled=True):
                api.admin.set_problem_availability(p["pid"], False)

            # Set bundles to enabled to set correct unlock behavior
            for b in api.problem.get_all_bundles():
                api.problem.set_bundle_dependencies_enabled(b["bid"], True)

        except Exception as e:
            print(e)
            sys.exit("Failed to load problems.")
    except:
        pass


if __name__ == "__main__":

    if len(sys.argv) != 2:
        print("Incorrect arguments passed, need")
        print("name")
        print(sys.argv)
        sys.exit("Bad args")
    else:
        _, name = sys.argv
        main(name)
