#!/usr/bin/env python3
import argparse
import glob
from importlib.machinery import SourceFileLoader
import time
from os.path import basename, splitext

import api


def load_modules(directory):
    files = glob.glob("{}/*.py".format(directory))
    return [
        SourceFileLoader(splitext(basename(module))[0], module).load_module()
        for module in files
    ]


def run_modules(modules, interval):
    while True:
        start_time = time.time()
        for module in modules:
            module.run()
        time.sleep(max(interval - (time.time() - start_time), 0))


def main():
    parser = argparse.ArgumentParser(description="CTF daemon manager")
    parser.add_argument(
        "-l", action="store_true", dest="show_list", help="List all daemons")
    parser.add_argument(
        "-a",
        "--all",
        dest="run_all",
        action="store_true",
        help="Run all daemons")
    parser.add_argument(
        "-i",
        "--interval",
        action="store",
        type=int,
        help="The interval in which to run the daemons",
        default=60)
    parser.add_argument(
        "-d",
        "--daemon-directory",
        action="store",
        help="The directory which contains the daemons",
        default="daemons")
    parser.add_argument("modules", nargs="*", help="The daemon modules to run")

    args = parser.parse_args()

    modules = load_modules(args.daemon_directory)

    if args.show_list:
        for module in modules:
            print(module.__name__)

    elif args.run_all:
        run_modules(modules, args.interval)

    else:
        if len(args.modules) == 0:
            parser.print_help()
            exit(1)

        selected_modules = [m for m in modules if m.__name__ in args.modules]
        if len(selected_modules) == 0:
            parser.print_help()
            exit(1)
        run_modules(selected_modules, args.interval)


main()
