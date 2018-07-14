"""A setuptools based setup module.

See:
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject
"""

import os
import sys
# To use a consistent encoding
from codecs import open
from os import path

# Always prefer setuptools over distutils
from setuptools import find_packages, setup

# Necessary to drop bins
if 'bdist_wheel' in sys.argv:
    raise RuntimeError("This setup.py does not support wheels")

here = path.abspath(path.dirname(__file__))

# Get the long description from the relevant file
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='ctf-web-api',

    # Versions should comply with PEP440.  For a discussion on single-sourcing
    # the version across setup.py and the project code, see
    # https://packaging.python.org/en/latest/single_source_version.html
    version='1.2.1',
    description="CTF Web Infrastructure",
    long_description=long_description,

    # The project's main homepage.
    url='https://github.com/picoCTF/picoCTF',

    # Author details
    author='Christopher Ganas',
    author_email='cganas@forallsecure.com',

    # Choose your license
    license='',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 3 - Alpha',

        # Indicate who your project is intended for
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],

    # What does your project relate to?
    keywords='ctf hacksports',

    # You can just specify the packages manually here if your project is
    # simple. Or you can use find_packages().
    packages=find_packages(exclude=['contrib', 'docs', 'tests*']),

    # List run-time dependencies here.  These will be installed by pip when
    # your project is installed. For an analysis of "install_requires" vs pip's
    # requirements files see:
    # https://packaging.python.org/en/latest/requirements.html
    install_requires=[
        'Flask==1.0.2',
        'Flask-Bcrypt==0.7.1',
        'Flask-Mail==0.9.1',
        'gunicorn==19.8.1',
        'line_profiler==2.1.2',
        'py==1.5.3',
        'pymongo==3.7.0',
        'pytest==3.6.1',
        'spur==0.3.20',
        'voluptuous==0.11.1',
    ],
    tests_require=["selenium"],
    entry_points={
        'console_scripts': [
            'api_manager=api.api_manager:main',
            'daemon_manager=api.daemon_manager:main',
        ],
    },
)
