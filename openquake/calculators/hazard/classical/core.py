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
Core functionality for the classical PSHA hazard calculator.
"""

import re

import kombu
import nhlib
import nhlib.calc
import nhlib.imt
import nhlib.site
import numpy

from django.db import transaction

from openquake import logs
from openquake import writer
from openquake.calculators.hazard import general
from openquake.db import models
from openquake.export import hazard as hexp
from openquake.input import logictree
from openquake.input import source
from openquake.utils import config
from openquake.utils import stats
from openquake.utils import tasks as utils_tasks

#: Default Spectral Acceleration damping. At the moment, this is not
#: configurable.
DEFAULT_SA_DAMPING = 5.0

    def export(self, *args, **kwargs):
        """Export to NRML"""
        logs.LOG.debug('> starting exports')

        if "exports" in kwargs and "xml" in kwargs["exports"]:
            hexp.curves2nrml(self.job.hazard_calculation.export_dir, self.job)

        logs.LOG.debug('< done with exports')


# Silencing 'Too many local variables'
# pylint: disable=R0914
@utils_tasks.oqtask
@stats.progress_indicator('h')
def hazard_curves(job_id, lt_rlz_id, src_ids):
    """
    Celery task for hazard curve calculator.

    Samples logic trees, gathers site parameters, and calls the hazard curve
    calculator.

    Once hazard curve data is computed, result progress updated (within a
    transaction, to prevent race conditions) in the
    `htemp.hazard_curve_progress` table.

    Once all of this work is complete, a signal will be sent via AMQP to let
    the control node know that the work is complete. (If there is any work left
    to be dispatched, this signal will indicate to the control node that more
    work can be enqueued.)

    :param int job_id:
        ID of the currently running job.
    :param lt_rlz_id:
        Id of logic tree realization model to calculate for.
    :param src_ids:
        List of ids of parsed source models to take into account.
    """
    logs.LOG.debug('> starting task: job_id=%s, lt_realization_id=%s'
                   % (job_id, lt_rlz_id))

    hc = models.HazardCalculation.objects.get(oqjob=job_id)

    lt_rlz = models.LtRealization.objects.get(id=lt_rlz_id)
    ltp = logictree.LogicTreeProcessor(hc.id)

    apply_uncertainties = ltp.parse_source_model_logictree_path(
            lt_rlz.sm_lt_path)
    gsims = ltp.parse_gmpe_logictree_path(lt_rlz.gsim_lt_path)

    sources = general.gen_sources(
        src_ids, apply_uncertainties, hc.rupture_mesh_spacing,
        hc.width_of_mfd_bin, hc.area_source_discretization)

    imts = im_dict_to_nhlib(hc.intensity_measure_types_and_levels)

    # Now initialize the site collection for use in the calculation.
    # If there is no site model defined, we will use the same reference
    # parameters (defined in the HazardCalculation) for every site.

    # TODO: We could just create the SiteCollection once, pickle it, and store
    # it in the DB (in SiteData). Creating the SiteCollection isn't an
    # expensive operation (at least for small calculations), but this is
    # wasted work.
    logs.LOG.debug('> creating site collection')
    site_coll = get_site_collection(hc)
    logs.LOG.debug('< done creating site collection')

    # Prepare args for the calculator.
    calc_kwargs = {'gsims': gsims,
                   'truncation_level': hc.truncation_level,
                   'time_span': hc.investigation_time,
                   'sources': sources,
                   'imts': imts,
                   'sites': site_coll}

    if hc.maximum_distance:
        dist = hc.maximum_distance
        calc_kwargs['source_site_filter'] = (
                nhlib.calc.filters.source_site_distance_filter(dist))
        calc_kwargs['rupture_site_filter'] = (
                nhlib.calc.filters.rupture_site_distance_filter(dist))

    # mapping "imt" to 2d array of hazard curves: first dimension -- sites,
    # second -- IMLs
    logs.LOG.debug('> computing hazard matrices')
    matrices = nhlib.calc.hazard_curve.hazard_curves_poissonian(**calc_kwargs)
    logs.LOG.debug('< done computing hazard matrices')

    logs.LOG.debug('> starting transaction')
    with transaction.commit_on_success():
        logs.LOG.debug('looping over IMTs')

        for imt in hc.intensity_measure_types_and_levels.keys():
            logs.LOG.debug('> updating hazard for IMT=%s' % imt)
            nhlib_imt = _imt_to_nhlib(imt)
            query = """
            SELECT * FROM htemp.hazard_curve_progress
            WHERE lt_realization_id = %s
            AND imt = %s
            FOR UPDATE"""
            [hc_progress] = models.HazardCurveProgress.objects.raw(
                query, [lt_rlz.id, imt])

            hc_progress.result_matrix = update_result_matrix(
                hc_progress.result_matrix, matrices[nhlib_imt])
            hc_progress.save()

            logs.LOG.debug('< done updating hazard for IMT=%s' % imt)

        # Before the transaction completes:

        # Check here if any of records in source progress model
        # with parsed_source_id from src_ids are marked as complete,
        # and rollback and abort if there is at least one
        src_prog = models.SourceProgress.objects.filter(
            lt_realization=lt_rlz, parsed_source__in=src_ids)

        if any(x.is_complete for x in src_prog):
            msg = (
                'One or more `source_progress` records were marked as '
                'complete. This was unexpected and probably means that the'
                ' calculation workload was not distributed properly.'
            )
            logs.LOG.critical(msg)
            transaction.rollback()
            raise RuntimeError(msg)

        # Mark source_progress records as complete
        src_prog.update(is_complete=True)

        # Update realiation progress,
        # mark realization as complete if it is done
        # First, refresh the logic tree realization record:
        lt_rlz = models.LtRealization.objects.get(id=lt_rlz.id)

        lt_rlz.completed_sources += len(src_ids)
        if lt_rlz.completed_sources == lt_rlz.total_sources:
            lt_rlz.is_complete = True

        lt_rlz.save()

    logs.LOG.debug('< transaction complete')

    # Last thing, signal back the control node to indicate the completion of
    # task. The control node needs this to manage the task distribution and
    # keep track of progress.
    logs.LOG.debug('< task complete, signalling completion')
    signal_task_complete(job_id, len(src_ids))


@staticmethod
def classical_task_arg_gen(hc, job, sources_per_task, progress):
    """
    Loop through realizations and sources to generate a sequence of
    task arg tuples. Each tuple of args applies to a single task.

    Yielded results are triples of (job_id, realization_id,
    source_id_list).

    :param hc:
        :class:`openquake.db.models.HazardCalculation` instance.
    :param job:
        :class:`openquake.db.models.OqJob` instance.
    :param int sources_per_task:
        The (max) number of sources to consider for each task.
    :param dict progress:
        A dict containing two integer values: 'total' and 'computed'. The task
        arg generator will update the 'total' count as the generator creates
        arguments.
    """
    realizations = models.LtRealization.objects.filter(
            hazard_calculation=hc, is_complete=False)

    for lt_rlz in realizations:
        source_progress = models.SourceProgress.objects.filter(
                is_complete=False, lt_realization=lt_rlz)
        source_ids = source_progress.values_list('parsed_source_id',
                                                 flat=True)
        progress['total'] += len(source_ids)

        for offset in xrange(0, len(source_ids), sources_per_task):
            task_args = (job.id, lt_rlz.id,
                         source_ids[offset:offset + sources_per_task])
            yield task_args




class ClassicalHazardCalculator(general.BaseHazardCalculatorNext):
    """
    Classical PSHA hazard calculator. Computes hazard curves for a given set of
    points.

    For each realization of the calculation, we randomly sample source models
    and GMPEs (Ground Motion Prediction Equations) from logic trees.
    """

    core_calc_task = hazard_curves
    task_arg_gen = classical_task_arg_gen

    def initialize_hazard_curve_progress(self, lt_rlz):
        """
        As a calculation progresses, workers will periodically update the
        intermediate results. These results will be stored in
        `htemp.hazard_curve_progress` until the calculation is completed.

        Before the core calculation begins, we need to initalize these records,
        one data set per IMT. Each dataset will be stored in the database as a
        pickled 2D numpy array (with number of rows == calculation points of
        interest and number of columns == number of IML values for a given
        IMT).

        We will create 1 `hazard_curve_progress` record per IMT per
        realization.

        :param lt_rlz:
            :class:`openquake.db.models.LtRealization` object to associate
            with these inital hazard curve values.
        """
        hc = self.job.hazard_calculation

        num_points = len(hc.points_to_compute())

        im_data = hc.intensity_measure_types_and_levels
        for imt, imls in im_data.items():
            hc_prog = models.HazardCurveProgress()
            hc_prog.lt_realization = lt_rlz
            hc_prog.imt = imt
            hc_prog.result_matrix = numpy.zeros((num_points, len(imls)))
            hc_prog.save()

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
            rlz_callback=self.initialize_hazard_curve_progress)

    def post_execute(self):
        """
        Create the final output records for hazard curves. This is done by
        copying the temporary results from `htemp.hazard_curve_progress` to
        `hzrdr.hazard_curve` (for metadata) and `hzrdr.hazard_curve_data` (for
        the actual curve PoE values). Foreign keys are made from
        `hzrdr.hazard_curve` to `hzrdr.lt_realization` (realization information
        is need to export the full hazard curve results).

        Finally, all data for the calculation which is stored in the `htemp`
        tables is deleted (at this point, it is no longer needed).
        """
        hc = self.job.hazard_calculation
        im = hc.intensity_measure_types_and_levels
        points = hc.points_to_compute()

        realizations = models.LtRealization.objects.filter(
            hazard_calculation=hc.id)

        for rlz in realizations:
            # create a new `HazardCurve` 'container' record for each
            # realization for each intensity measure type
            for imt, imls in im.items():
                sa_period = None
                sa_damping = None
                if 'SA' in imt:
                    match = re.match(r'^SA\(([^)]+?)\)$', imt)
                    sa_period = float(match.group(1))
                    sa_damping = DEFAULT_SA_DAMPING
                    hc_im_type = 'SA'  # don't include the period
                else:
                    hc_im_type = imt

                hco = models.Output(
                    owner=hc.owner,
                    oq_job=self.job,
                    display_name="hc-rlz-%s" % rlz.id,
                    output_type='hazard_curve',
                )
                hco.save()

                haz_curve = models.HazardCurve(
                    output=hco,
                    lt_realization=rlz,
                    investigation_time=hc.investigation_time,
                    imt=hc_im_type,
                    imls=imls,
                    sa_period=sa_period,
                    sa_damping=sa_damping,
                )
                haz_curve.save()

                [hc_progress] = models.HazardCurveProgress.objects.filter(
                    lt_realization=rlz.id, imt=imt)

                hc_data_inserter = writer.BulkInserter(models.HazardCurveData)
                for i, location in enumerate(points):
                    poes = hc_progress.result_matrix[i]
                    hc_data_inserter.add_entry(
                        hazard_curve_id=haz_curve.id,
                        poes=poes.tolist(),
                        location=location.wkt2d)

                hc_data_inserter.flush()

        # delete temporary data
        models.HazardCurveProgress.objects.filter(
            lt_realization__hazard_calculation=hc.id).delete()
        models.SourceProgress.objects.filter(
            lt_realization__hazard_calculation=hc.id).delete()
        models.SiteData.objects.filter(hazard_calculation=hc.id).delete()


def update_result_matrix(current, new):
    """
    Use the following formula to combine multiple iterations of results:

    `result = 1 - (1 - current) * (1 - new)`

    This is used to incrementally update hazard curve results by combining an
    initial value with some new results. (Each set of new results is computed
    over only a subset of seismic sources defined in the calculation model.)

    Parameters are expected to be multi-dimensional numpy arrays, but the
    formula will also work with scalars.

    :param current:
        Numpy array representing the current result matrix value.
    :param new:
        Numpy array representing the new results which need to be combined with
        the current value. This should be the same shape as `current`.
    """
    return 1 - (1 - current) * (1 - new)


def get_site_collection(hc):
    """
    Create a `SiteCollection`, which is needed by nhlib to compute hazard
    curves.

    :param hc:
        Instance of a :class:`~openquake.db.models.HazardCalculation`. We need
        this in order to get the points of interest for a calculation as well
        as load pre-computed site data or access reference site parameters.

    :returns:
        :class:`nhlib.site.SiteCollection` instance.
    """
    site_data = models.SiteData.objects.filter(hazard_calculation=hc.id)
    if len(site_data) > 0:
        site_data = site_data[0]
        sites = zip(site_data.lons, site_data.lats, site_data.vs30s,
                    site_data.vs30_measured, site_data.z1pt0s,
                    site_data.z2pt5s)
        sites = [nhlib.site.Site(
            nhlib.geo.Point(lon, lat), vs30, vs30m, z1pt0, z2pt5)
            for lon, lat, vs30, vs30m, z1pt0, z2pt5 in sites]
    else:
        # Use the calculation reference parameters to make a site collection.
        points = hc.points_to_compute()
        measured = hc.reference_vs30_type == 'measured'
        sites = [
            nhlib.site.Site(pt, hc.reference_vs30_value, measured,
                            hc.reference_depth_to_2pt5km_per_sec,
                            hc.reference_depth_to_1pt0km_per_sec)
            for pt in points]

    return nhlib.site.SiteCollection(sites)



def signal_task_complete(job_id, num_sources):
    """
    Send a signal back through a dedicated queue to the 'control node' to
    notify of task completion and the number of sources computed.

    Signalling back this metric is needed to tell the control node when it can
    conclude its `execute` phase.

    :param int job_id:
        ID of a currently running :class:`~openquake.db.models.OqJob`.
    :param int num_sources:
        Number of sources computed in the completed task.
    """
    # The job ID may be redundant (since it's in the routing key), but
    # we can put this here for a sanity check on the receiver side.
    # Maybe we can remove this
    msg = dict(job_id=job_id, num_sources=num_sources)

    exchange, conn_args = general.exchange_and_conn_args()

    routing_key = general.ROUTING_KEY_FMT % dict(job_id=job_id)

    with kombu.BrokerConnection(**conn_args) as conn:
        with conn.Producer(exchange=exchange,
                           routing_key=routing_key) as producer:
            producer.publish(msg)


def im_dict_to_nhlib(im_dict):
    """
    Given the dict of intensity measure types and levels, convert them to a
    dict with the same values, except create :mod:`mhlib.imt` objects for the
    new keys.

    :returns:
        A dict of intensity measure level lists, keyed by an IMT object. See
        :mod:`nhlib.imt` for more information.
    """
    # TODO: file a bug about  SA periods in nhlib imts.
    # Why are values of 0.0 not allowed? Technically SA(0.0) means PGA, but
    # there must be a reason why we can't do this.
    nhlib_im = {}

    for imt, imls in im_dict.items():
        nhlib_imt = _imt_to_nhlib(imt)
        nhlib_im[nhlib_imt] = imls

    return nhlib_im


def _imt_to_nhlib(imt):
    """Covert an IMT string to an nhlib object.

    :param str imt:
        Given the IMT string (defined in the job config file), convert it to
        equivlent nhlib object. See :mod:`nhlib.imt`.
    """
    if 'SA' in imt:
        match = re.match(r'^SA\(([^)]+?)\)$', imt)
        period = float(match.group(1))
        return nhlib.imt.SA(period, DEFAULT_SA_DAMPING)
    else:
        imt_class = getattr(nhlib.imt, imt)
        return imt_class()
