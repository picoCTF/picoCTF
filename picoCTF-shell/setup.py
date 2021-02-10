"""A setuptools based setup module.

See:
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject
"""

import sys

# To use a consistent encoding
from codecs import open
from os import path

# Always prefer setuptools over distutils
from setuptools import find_packages, setup

here = path.abspath(path.dirname(__file__))

# Get the long description from the relevant file
try:
    with open(path.join(here, "README.md"), encoding="utf-8") as f:
        long_description = f.read()
except FileNotFoundError:
    long_description = "picoCTF shell_manager and hacksport"

setup(
    name="ctf-shell-manager",
    # Versions should comply with PEP440.  For a discussion on single-sourcing
    # the version across setup.py and the project code, see
    # https://packaging.python.org/en/latest/single_source_version.html
    version="1.2.1",
    description="deploy and package hacksport problems",
    long_description=long_description,
    # The project's main homepage.
    url="https://github.com/picoCTF/picoCTF",
    # Author details
    author="Christopher Ganas",
    author_email="cganas@forallsecure.com",
    # Choose your license
    license="MIT",
    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        "Development Status :: 3 - Alpha",
        # Indicate who your project is intended for
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Build Tools",
        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        "Programming Language :: Python :: 3.7",
    ],
    # What does your project relate to?
    keywords="ctf hacksports",
    # You can just specify the packages manually here if your project is
    # simple. Or you can use find_packages().
    packages=find_packages(exclude=["contrib", "docs", "tests*"]),
    # List run-time dependencies here.  These will be installed by pip when
    # your project is installed. For an analysis of "install_requires" vs pip's
    # requirements files see:
    # https://packaging.python.org/en/latest/requirements.html
    install_requires=[
        "coloredlogs==10.0",
        "cryptography==3.3.2",
        "docker[tls]==4.2.0",
        "Flask==1.1.1",
        "idna<3",
        "Jinja2==2.10.1",
        "openssh-wrapper==0.4",
        "psutil==5.6.6",
        "pytest==3.6.1",
        "spur==0.3.21",
        "voluptuous==0.11.7",
        "Werkzeug==0.15.5",
    ],
    extras_require={"dev": ["black", "flake8", "pydocstyle"]},
    # To provide executable scripts, use entry points in preference to the
    # "scripts" keyword. Entry points provide cross-platform support and allow
    # pip to create the appropriate form of executable for the target platform.
    entry_points={"console_scripts": ["shell_manager=shell_manager.run:main"]},
    # Include static files listed in Manifest.in
    include_package_data=True,
)
