# -*- coding: utf-8 -*-
# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2010-2014, GEM Foundation.
#
# OpenQuake is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OpenQuake is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with OpenQuake.  If not, see <http://www.gnu.org/licenses/>.


"""
Config for all installed OpenQuake binaries and modules.
Should be installed by setup.py into /etc/openquake
eventually.
"""

import os
import sys

# just in the case that are you using oq-engine from sources
# with the rest of oq libraries installed into the system (or a
# virtual environment) you must set this environment variable
if os.environ.get("OQ_ENGINE_USE_SRCDIR"):
    sys.modules['openquake'].__dict__["__path__"].insert(
        0, os.path.join(os.path.dirname(__file__), "openquake"))

import celery
from openquake.engine.utils import config, get_core_modules
from openquake import engine

config.abort_if_no_config_available()

sys.path.insert(0, os.path.dirname(__file__))

amqp = config.get_section("amqp")

if celery.__version__ < '3.0.0':  # old version in Ubuntu 12.04
    BROKER_HOST = amqp.get("host")
    BROKER_PORT = int(amqp.get("port"))
    BROKER_USER = amqp.get("user")
    BROKER_PASSWORD = amqp.get("password")
    BROKER_VHOST = amqp.get("vhost")
else:
    BROKER_URL = 'amqp://%(user)s:%(password)s@%(host)s:%(port)s/%(vhost)s' % \
                 amqp

# BROKER_POOL_LIMIT enables a connections pool so Celery can reuse
# a single connection to RabbitMQ. Value 10 is the default from
# Celery 2.5 where this feature is enabled by default.
# Actually disabled because it's not stable in production.
# See https://bugs.launchpad.net/oq-engine/+bug/1250402
BROKER_POOL_LIMIT = None

CELERY_RESULT_BACKEND = "amqp"

# CELERY_ACKS_LATE and CELERYD_PREFETCH_MULTIPLIER settings help evenly
# distribute tasks across the cluster. This configuration is intended
# make worker processes reserve only a single task at any given time.
# (The default settings for prefetching define that each worker process will
# reserve 4 tasks at once. For long running calculations with lots of long,
# heavy tasks, this greedy prefetching is not recommended and can result in
# performance issues with respect to cluster utilization.)
# CELERY_MAX_CACHED_RESULTS disable the cache on the results: this means
# that map_reduce will not leak memory by keeping the intermediate results
CELERY_ACKS_LATE = True
CELERYD_PREFETCH_MULTIPLIER = 1
CELERY_MAX_CACHED_RESULTS = 1

CELERY_ACCEPT_CONTENT = ['pickle', 'json']

CELERY_IMPORTS = get_core_modules(engine) + [
    "openquake.engine.calculators.hazard.general",
    "openquake.engine.tests.utils.tasks"] + [
    "openquake.commonlib.calculators.event_loss",
    "openquake.commonlib.calculators.event_based",
    "openquake.commonlib.calculators.scenario_risk",
    "openquake.commonlib.calculators.scenario_damage",
    "openquake.commonlib.calculators.classical_damage",
    "openquake.commonlib.calculators.classical_risk",
    ]

os.environ["DJANGO_SETTINGS_MODULE"] = "openquake.engine.settings"
os.environ['OQ_ENGINE_MODE'] = '1'

try:
    from openquake.engine.utils import tasks
    # as a side effect, this import replaces the litetask with oqtask
    # this is hackish, but bear with until we remove the old calculators
except ImportError:  # circular import with celery 2, only affecting nose
    pass
