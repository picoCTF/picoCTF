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

# Necessary to drop bins
if "bdist_wheel" in sys.argv:
    raise RuntimeError("This setup.py does not support wheels")

here = path.abspath(path.dirname(__file__))

# Get the long description from the relevant file
with open(path.join(here, "README.md"), encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="ctf-web-api",
    # Versions should comply with PEP440.  For a discussion on single-sourcing
    # the version across setup.py and the project code, see
    # https://packaging.python.org/en/latest/single_source_version.html
    version="2.0.0",
    description="picoCTF web API",
    long_description=long_description,
    # The project's main homepage.
    url="https://github.com/picoCTF/picoCTF",
    # Author details
    author="picoCTF team",
    author_email="opensource@picoctf.com",
    # Choose your license
    license="",
    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        "Development Status :: 4 - Beta",
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
        "bs4==0.0.1",
        "cchardet==2.1.4",
        "docker[tls]==4.2.0",
        "eventlet==0.25.1",
        "Flask==1.1.1",
        "Flask-Bcrypt==0.7.1",
        "Flask-Mail==0.9.1",
        "flask-restplus==0.13.0",
        "gunicorn==19.9.0",
        "marshmallow==3.0.1",
        "py==1.10.0",
        "pymongo==4.6.3",
        "spur==0.3.21",
        "voluptuous==0.11.7",
        "walrus==0.7.1",
        "werkzeug<=0.16.1"
    ],
    extras_require={
        "dev": [
            "black",
            "flake8",
            "locustio",
            "pydocstyle",
            "pytest",
            "pytest-cov",
            "pytest-mongo",
            "pytest-redis",
        ]
    },
    entry_points={"console_scripts": ["daemon_manager=daemon_manager:main"]},
)
