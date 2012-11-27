# -*- coding: utf-8 -*-
# Copyright (c) 2010-2012, GEM Foundation.
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
Disaggregation calculator core functionality
"""

from django.db import transaction

from openquake import logs
from openquake.calculators.hazard import general as haz_general
from openquake.calculators.hazard.classical import core as classical
from openquake.db import models
from openquake.utils import config
from openquake.utils import general as general_utils
from openquake.utils import stats
from openquake.utils import tasks as utils_tasks


@utils_tasks.oqtask
@stats.count_progress('h')
def disagg_task(job_id, block, lt_rlz_id, calc_type):
    """
    Task wrapper around core hazard curve/disaggregation computation functions.

    :param int job_id:
        ID of the currently running job.
    :param block:
        A sequence of work items for this task to process. In the case of
        hazard curve computation, this is a sequence of source IDs. In the case
        of disaggregation, this is a list of points.

        For more info, see
        :func:`openquake.calculators.hazard.classical.core.compute_hazard_curves`
        if ``calc_type`` is 'hazard_curve' and :func:`compute_disagg` if
        ``calc_type`` is 'disagg'.
    :param lt_rlz_id:
        ID of the :class:`openquake.db.models.LtRealization` for this part of
        the computation.
    :param calc_type:
        'hazard_curve' or 'disagg'. This indicates more or less the calculation
        phase; first we must computed all of the hazard curves, then we can
        compute the disaggregation histograms.
    """
    result = None
    if calc_type == 'hazard_curve':
        result = classical.compute_hazard_curves(job_id, block, lt_rlz_id)
    elif calc_type == 'disagg':
        result = compute_disagg(job_id, block, lt_rlz_id)
    else:
        msg = ('Invalid calculation type "%s";'
               ' expected "hazard_curve" or "disagg"')
        msg %= calc_type
        raise RuntimeError(msg)

    haz_general.signal_task_complete(
        job_id=job_id, num_items=len(block), calc_type=calc_type)

    return result


def compute_disagg(job_id, points, lt_rlz_id):
    logs.LOG.debug(
        '> computing disaggregation for %(np)s points for realization %(rlz)s'
        % dict(np=len(points), rlz=lt_rlz_id))

    with transaction.commit_on_success():
        # Update realiation progress,
        # mark realization as complete if it is done
        # First, refresh the logic tree realization record:
        ltr_query = """
        SELECT * FROM hzrdr.lt_realization
        WHERE id = %s
        FOR UPDATE
        """

        [lt_rlz] = models.LtRealization.objects.raw(
            ltr_query, [lt_rlz_id])

        lt_rlz.completed_items += len(points)
        if lt_rlz.completed_items == lt_rlz.total_items:
            lt_rlz.is_complete = True

        lt_rlz.save()

    logs.LOG.debug('< done computing disaggregation')
    return None


class DisaggHazardCalculator(haz_general.BaseHazardCalculatorNext):

    core_calc_task = disagg_task

    def __init__(self, *args, **kwargs):
        super(DisaggHazardCalculator, self).__init__(*args, **kwargs)

        # Progress counters for hazard curve computation:
        self.progress['hc_total'] = 0
        self.progress['hc_computed'] = 0

        # Flag to indicate that the computation has reached the disaggregation
        # phase. Prior to this, the hazard curve computation phase must be
        # completed.
        self.disagg_phase = False

    def pre_execute(self):
        """
        Do pre-execution work. At the moment, this work entails: parsing and
        initializing sources, parsing and initializing the site model (if there
        is one), and generating logic tree realizations. (The latter piece
        basically defines the work to be done in the `execute` phase.)
        """
        # Parse logic trees and create source Inputs.
        self.initialize_sources()

        # Deal with the site model and compute site data for the calculation
        # (if a site model was specified, that is).
        self.initialize_site_model()

        # Now bootstrap the logic tree realizations and related data.
        # This defines for us the "work" that needs to be done when we reach
        # the `execute` phase.
        # This will also stub out hazard curve result records. Workers will
        # update these periodically with partial results (partial meaning,
        # result curves for just a subset of the overall sources) when some
        # work is complete.
        self.initialize_realizations(
            rlz_callbacks=[self.initialize_hazard_curve_progress])

        self.record_init_stats()

        # Set the progress counters:
        num_sources = models.SourceProgress.objects.filter(
            is_complete=False,
            lt_realization__hazard_calculation=self.hc).count()
        self.progress['total'] += num_sources
        self.progress['hc_total'] = num_sources

        realizations = models.LtRealization.objects.filter(
            hazard_calculation=self.hc, is_complete=False)
        num_rlzs = realizations.count()
        num_points = len(self.hc.points_to_compute())
        self.progress['total'] += num_rlzs * num_points

        # Update the progress info on the realizations, to include the disagg
        # phase:
        for rlz in realizations:
            rlz.total_items += num_points
            rlz.save()

        self.initialize_pr_data()

    def task_arg_gen(self, block_size):
        """
        Generate task args for the first phase of the disaggregation
        calculations. This phase is concerned with computing hazard curves,
        which must be completed in full before disaggregation calculation
        can begin.

        See also :meth:`disagg_task_arg_gen`.

        :param int block_size:
            The number of items per task. In this case, this the number of
            sources for hazard curve calc task, or number of sites for disagg
            calc tasks.
        """
        realizations = models.LtRealization.objects.filter(
            hazard_calculation=self.hc, is_complete=False)

        # first, distribute tasks for hazard curve computation
        for lt_rlz in realizations:
            source_progress = models.SourceProgress.objects.filter(
                is_complete=False, lt_realization=lt_rlz).order_by('id')
            source_ids = source_progress.values_list(
                'parsed_source_id', flat=True)

            for block in general_utils.block_splitter(source_ids, block_size):
                # job_id, source id block, lt rlz, calc_type
                yield (self.job.id, block, lt_rlz.id, 'hazard_curve')

    def disagg_task_arg_gen(self, block_size):
        """
        Generate task args for the second phase of disaggregation calculations.
        This phase is concerned with computing the disaggregation histograms.

        :param int block_size:
            The number of items per task. In this case, this the number of
            sources for hazard curve calc task, or number of sites for disagg
            calc tasks.
        """
        realizations = models.LtRealization.objects.filter(
            hazard_calculation=self.hc, is_complete=False)

        # then distribute tasks for disaggregation histogram computation
        all_points = list(self.hc.points_to_compute())
        for lt_rlz in realizations:
            for block in general_utils.block_splitter(all_points, block_size):
                # job_id, point block, lt rlz, calc_type
                yield (self.job.id, block, lt_rlz.id, 'disagg')

    def get_task_complete_callback(self, hc_task_arg_gen, block_size,
                                   concurrent_tasks):
        """
        Overrides the default task complete callback, defined in the super
        class.

        The ``hc_task_arg_gen`` pass here is the arg gen for the first phase of
        the calculation. This method also handles task generation for the
        second phase.

        :param int concurrent_tasks:
            The (maximum) number of tasks that should be in queue at any time.
            This parameter is used when the calculation phase changes from
            `hazard_curve` to `disagg`, and the queue needs to be filled up
            completely with disagg tasks.

        See
        :meth:`openquake.calculators.hazard.general.BaseHazardCalculatorNext.get_task_complete_callback`
        for more info about the expected input and output.
        """
        # prep the disaggregation task arg gen for the second phase of the
        # calculation
        disagg_task_arg_gen = self.disagg_task_arg_gen(block_size)

        def callback(body, message):
            """
            :param dict body:
                ``body`` is the message sent by the task. The dict should
                contain 2 keys: `job_id` and `num_sources` (to indicate the
                number of sources computed).

                Both values are `int`.
            :param message:
                A :class:`kombu.transport.pyamqplib.Message`, which contains
                metadata about the message (including content type, channel,
                etc.). See kombu docs for more details.
            """
            job_id = body['job_id']
            num_items = body['num_items']
            calc_type = body['calc_type']

            assert job_id == self.job.id

            # Log a progress message
            logs.log_percent_complete(job_id, 'hazard')

            if self.disagg_phase:
                assert calc_type == 'disagg'
                # We're in the second phase of the calculation; just keep
                # queuing tasks (if there are any left) and wait for everything
                # to finish.
                try:
                    haz_general.queue_next(
                        self.core_calc_task, disagg_task_arg_gen.next())
                except StopIteration:
                    # There are no more tasks to dispatch; now we just need to
                    # wait until all of the tasks signal completion.
                    pass
                else:
                    logs.LOG.debug('* queuing the next disagg task')
            else:
                if calc_type == 'hazard_curve':
                    # record progress specifically for hazard curve computation

                    self.progress['hc_computed'] += num_items

                    if (self.progress['hc_computed']
                        == self.progress['hc_total']):
                        # we're switching to disagg phase
                        self.disagg_phase = True
                        logs.LOG.debug('* switching to disaggregation phase')

                        # Finalize the hazard curves, so the disaggregation
                        # can find curves by their point geometry:
                        self.finalize_hazard_curves()

                        logs.LOG.debug('* queuing initial disagg tasks')
                        # the task queue should be empty, so let's fill it up
                        # with disagg tasks:
                        for _ in xrange(concurrent_tasks):
                            try:
                                haz_general.queue_next(
                                    self.core_calc_task,
                                    disagg_task_arg_gen.next())
                            except StopIteration:
                                # If we get a `StopIteration` here, that means
                                # we have number of disagg tasks <
                                # concurrent_tasks.
                                break
                    else:
                        # we're not done computing hazard curves; enqueue the
                        # next task
                        try:
                            haz_general.queue_next(
                                self.core_calc_task, hc_task_arg_gen.next())
                        except StopIteration:
                            # No more hazard curve tasks left to enqueue;
                            # now we just wait for this phase to complete.
                            pass
                        else:
                            logs.LOG.debug(
                                '* queueing the next hazard curve task')
                else:
                    # we're in the hazard curve phase, but the completed
                    # message did not have a  'hazard_curve' type
                    raise RuntimeError(
                        'Unexpected message `calc_type`: "%s"' % calc_type)

            # Last thing, update the 'computed' counter and acknowledge the
            # message:
            self.progress['computed'] += num_items
            message.ack()

        return callback

    def clean_up(self):
        """
        Delete temporary database records. These records represent intermediate
        copies of final calculation results and are no longer needed.

        In this case, this includes all of the data for this calculation in the
        tables found in the `htemp` schema space.
        """
        logs.LOG.debug('> cleaning up temporary DB data')
        models.HazardCurveProgress.objects.filter(
            lt_realization__hazard_calculation=self.hc.id).delete()
        models.SourceProgress.objects.filter(
            lt_realization__hazard_calculation=self.hc.id).delete()
        models.SiteData.objects.filter(hazard_calculation=self.hc.id).delete()
        logs.LOG.debug('< done cleaning up temporary DB data')
