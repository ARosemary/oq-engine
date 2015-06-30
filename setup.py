# The OpenQuake Engine
# Copyright (C) 2010-2015, GEM Foundation
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
import re
import sys
from setuptools import setup, find_packages


def get_version():
    version_re = r"^__version__\s+=\s+['\"]([^'\"]*)['\"]"
    version = None

    package_init = 'openquake/engine/__init__.py'
    for line in open(package_init, 'r'):
        version_match = re.search(version_re, line, re.M)
        if version_match:
            version = version_match.group(1)
            break
    else:
        sys.exit('__version__ variable not found in %s' % package_init)

    return version

version = get_version()

url = "https://github.com/gem/oq-engine"

README = """
OpenQuake is an open source application that allows users to
compute seismic hazard and seismic risk of earthquakes on a global scale.

Please note: the /usr/bin/oq-engine script requires a celeryconfig.py file in
the PYTHONPATH; when using binary packages, if a celeryconfig.py is not
available the OpenQuake Engine default celeryconfig.py, located in
/usr/share/openquake/engine, is used.

Copyright (C) 2010-2015, GEM Foundation.
"""

PY_MODULES = ['openquake.engine.bin.openquake_cli']

setup(
    entry_points={
        "console_scripts": [
            "oq-engine = openquake.engine.bin.openquake_cli:main"
        ]
    },
    name="openquake.engine",
    version=version,
    author="GEM Foundation",
    author_email="devops@openquake.org",
    maintainer='GEM Foundation',
    maintainer_email='devops@openquake.org',
    description=("Computes hazard, risk and socio-economic impact of "
                 "earthquakes."),
    license="AGPL3",
    keywords="earthquake seismic hazard risk",
    url=url,
    long_description=README,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Education',
        'Intended Audience :: Science/Research',
        'Programming Language :: Python :: 2',
        'License :: OSI Approved :: GNU Affero General Public License v3',
        'Operating System :: OS Independent',
        'Topic :: Scientific/Engineering',
    ],
    packages=find_packages(exclude=["qa_tests", "qa_tests.*",
                                    "tools",
                                    "openquake.engine.bin",
                                    "openquake.engine.bin.*"]),
    py_modules=PY_MODULES,
    include_package_data=True,
    package_data={"openquake.engine": [
        "openquake.cfg", "openquake_worker.cfg",
        "README.md", "LICENSE", "CONTRIBUTORS.txt"]},
    namespace_packages=['openquake'],
    scripts=["openquake/engine/bin/oq_create_db"],
    zip_safe=False,
    )
