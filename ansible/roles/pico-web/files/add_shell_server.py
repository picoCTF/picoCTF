#!/usr/bin/env python3

# Simple script to programmatically add a shell server to a running picoCTF web
# instance.  If using a custom APP_SETTINGS_FILE, ensure the appropriate
# environment variable is set prior to running this script. This script is best
# run from the pico-web role (ansible/roles/pico-web/tasks/main.yml)

import sys

# The picoCTF API
import api


def main(name, host, user, password, port, proto):
    try:
        # If a server by this name exists no action necessary
        api.shell_servers.get_server(name=name)
    except:
        try:
            sid = api.shell_servers.add_server({
                "name": name,
                "host": host,
                "port": port,
                "username": user,
                "password": password,
                "protocol": proto,
                "server_number": 1
            })
        except Exception as e:
            print(e)
            sys.exit("Failed to connect to shell server.")


if __name__ == "__main__":
    if len(sys.argv) != 7:
        print("Incorrect arguments passed, need")
        print("name, host, user, password, port, proto")
        print(sys.argv)
        sys.exit("Bad args")
    else:
        _, name, host, user, password, port, proto = sys.argv
        main(name, host, user, password, port, proto)
