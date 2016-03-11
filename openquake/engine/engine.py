# -*- coding: utf-8 -*-
# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright (C) 2010-2016 GEM Foundation
#
# OpenQuake is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OpenQuake is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with OpenQuake. If not, see <http://www.gnu.org/licenses/>.

"""Engine: A collection of fundamental functions for initializing and running
calculations."""

import sys
import traceback
from datetime import datetime

from openquake.commonlib import valid
from openquake.commonlib.oqvalidation import OqParam
from openquake.engine import logs
from openquake.engine.utils import config, tasks
from openquake.server.db import actions


def dbserver(action, *args):
    """
    A fake dispatcher to the database server.

    :param action: database action to perform
    :param args: arguments
    """
    return getattr(actions, action)(*args)

TERMINATE = valid.boolean(
    config.get('celery', 'terminate_workers_on_revoke') or 'false')

USE_CELERY = valid.boolean(config.get('celery', 'use_celery') or 'false')

if USE_CELERY:
    import celery.task.control

    def set_concurrent_tasks_default():
        """
        Set the default for concurrent_tasks to twice the number of workers.
        Returns the number of live celery nodes (i.e. the number of machines).
        """
        stats = celery.task.control.inspect(timeout=1).stats()
        if not stats:
            sys.exit("No live compute nodes, aborting calculation")
        num_cores = sum(stats[k]['pool']['max-concurrency'] for k in stats)
        OqParam.concurrent_tasks.default = 2 * num_cores
        logs.LOG.info('Using %s, %d cores',
                      ', '.join(sorted(stats)), num_cores)

    def celery_cleanup(job, terminate, task_ids=()):
        """
        Release the resources used by an openquake job.
        In particular revoke the running tasks (if any).

        :param int job_id: the job id
        :param bool terminate: the celery revoke command terminate flag
        :param task_ids: celery task IDs
        """
        # Using the celery API, terminate and revoke and terminate any running
        # tasks associated with the current job.
        if task_ids:
            logs.LOG.warn('Revoking %d tasks', len(task_ids))
        else:  # this is normal when OQ_NO_DISTRIBUTE=1
            logs.LOG.debug('No task to revoke')
        for tid in task_ids:
            celery.task.control.revoke(tid, terminate=terminate)
            logs.LOG.debug('Revoked task %s', tid)


# used by bin/openquake and openquake.server.views
def run_calc(job, log_level, log_file, exports, hazard_calculation_id=None):
    """
    Run a calculation.

    :param job:
        :class:`openquake.server.db.model.OqJob` instance
    :param str log_level:
        The desired logging level. Valid choices are 'debug', 'info',
        'progress', 'warn', 'error', and 'critical'.
    :param str log_file:
        Complete path (including file name) to file where logs will be written.
        If `None`, logging will just be printed to standard output.
    :param exports:
        A comma-separated string of export types.
    """
    if USE_CELERY:
        set_concurrent_tasks_default()
    with logs.handle(job, log_level, log_file):  # run the job
        tb = 'None\n'
        try:
            _do_run_calc(job, exports, hazard_calculation_id)
            job.status = 'complete'
        except:
            tb = traceback.format_exc()
            try:
                logs.LOG.critical(tb)
                job.status = 'failed'
            except:  # an OperationalError may always happen
                sys.stderr.write(tb)
            raise
        finally:
            # try to save the job stats on the database and then clean up;
            # if there was an error in the calculation, this part may fail;
            # in such a situation, we simply log the cleanup error without
            # taking further action, so that the real error can propagate
            try:
                job.is_running = False
                job.stop_time = datetime.utcnow()
                job.save()
                if USE_CELERY:
                    celery_cleanup(
                        job, TERMINATE, tasks.OqTaskManager.task_ids)
            except:
                # log the finalization error only if there is no real error
                if tb == 'None\n':
                    logs.LOG.error('finalizing', exc_info=True)
        dbserver('expose_outputs', job.calc.datastore, job)
    return job.calc


# keep this as a private function, since it is mocked by engine_test.py
def _do_run_calc(job, exports, hazard_calculation_id):
    with job.calc.monitor:
        job.calc.run(exports=exports,
                     hazard_calculation_id=hazard_calculation_id)
