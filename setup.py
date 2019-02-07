#!/usr/bin/env python
import configparser
from setuptools import find_packages, setup

SRC_PREFIX = 'src'

packages = find_packages(SRC_PREFIX)


def readme():
    with open('README.md') as f:
        return f.read()


def get_required_packages():
    """
    Returns the packages used for install_requires
    This used to pin down every package in Pipfile.lock to the version, but that, in turn, broke
    downstream projects because it was way too strict.
    Now, this simply grabs all the items listed in the `Pipfile` `[packages]` section without version
    pinning
    """
    install_requires = []

    config = configparser.ConfigParser()
    config.read('Pipfile')

    install_requires = sorted([x for x in config['packages']])

    return install_requires


setup(
    name='git-smash',
    url='https://github.com/openslate/git-smash',
    author='OpenSlate',
    author_email='code@openslate.com',
    version='0.0.0',
    description='smash multiple feature branches into an ephemeral branch',
    long_description=readme(),
    long_description_content_type='text/markdown',
    package_dir={'': 'src'},
    packages=packages,
    entry_points={
        'console_scripts': [
            'git-smash = git_smash.entrypoints:git_smash',
        ],
    },
    install_requires=get_required_packages()
)
