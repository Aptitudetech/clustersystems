# -*- coding: utf-8 -*-
from setuptools import setup, find_packages
import re, ast

try:
    from pip._internal.req import parse_requirements
except ImportError:
    from pip.req import parse_requirements

# get version from __version__ variable in cs/__init__.py
_version_re = re.compile(r'__version__\s+=\s+(.*)')

with open('cs/__init__.py', 'rb') as f:
    version = str(ast.literal_eval(_version_re.search(
        f.read().decode('utf-8')).group(1)))

requirements = parse_requirements("requirements.txt", session="")

setup(
	name='cs',
	version=version,
	description='Cluster Systems',
	author='aptitudetech',
	author_email='info@aptitudetech.net',
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=[str(ir.req) for ir in requirements],
	dependency_links=[str(ir._link) for ir in requirements if ir._link]
)
