# 2015.06.26 13:21:50 CEST
"""
Utilities to build a report writer generating a .rst report for a calculation
"""
from __future__ import print_function
import os
import sys
import mock
import logging


from openquake.baselib.general import humansize
from openquake.commonlib import readinput, datastore, source, parallel
from openquake.commonlib.oqvalidation import OqParam
from openquake.calculators import base, views


def indent(text):
    return '  ' + '\n  '.join(text.splitlines())


class ReportWriter(object):
    """
    A particularly smart view over the datastore
    """
    title = dict(
        params='Parameters',
        inputs='Input files',
        csm_info='Composite source model',
        required_params_per_trt='Required parameters per tectonic region type',
        rupture_collections='Non-empty rupture collections',
        col_rlz_assocs='Collections <-> realizations',
        ruptures_per_trt='Number of ruptures per tectonic region type',
        rlzs_assoc='Realizations per (TRT, GSIM)',
        source_data_transfer='Expected data transfer for the sources',
        avglosses_data_transfer='Estimated data transfer for the avglosses',
        exposure_info='Exposure model',
        short_source_info='Slowest sources',
        performance='Slowest operations',
    )

    def __init__(self, dstore):
        self.dstore = dstore
        self.oq = oq = OqParam.from_(dstore.attrs)
        self.text = oq.description + '\n' + '=' * len(oq.description)
        # NB: in the future, the sitecol could be transferred as
        # an array by leveraging the HDF5 serialization protocol in
        # litetask decorator; for the moment however the size of the
        # data to transfer is given by the usual pickle
        sitecol_size = humansize(len(parallel.Pickled(dstore['sitecol'])))
        self.text += '\n\nnum_sites = %d, sitecol = %s' % (
            len(dstore['sitemesh']), sitecol_size)

    def add(self, name, obj=None):
        """Add the view named `name` to the report text"""
        title = self.title[name]
        line = '-' * len(title)
        if obj:
            text = '\n::\n\n' + indent(str(obj))
        else:
            orig = views.rst_table.__defaults__
            views.rst_table.__defaults__ = (None, '%s')  # disable formatting
            text = datastore.view(name, self.dstore)
            views.rst_table.__defaults__ = orig
        self.text += '\n'.join(['\n\n' + title, line, text])

    def make_report(self):
        """Build the report and return a restructed text string"""
        oq, ds = self.oq, self.dstore
        for name in ('params', 'inputs'):
            self.add(name)
        if 'composite_source_model' in ds:
            self.add('csm_info')
            self.add('required_params_per_trt')
        self.add('rlzs_assoc', ds['rlzs_assoc'])
        if 'num_ruptures' in ds:
            self.add('rupture_collections')
            self.add('col_rlz_assocs')
        elif 'composite_source_model' in ds:
            self.add('ruptures_per_trt')
        if 'scenario' not in oq.calculation_mode:
            self.add('source_data_transfer')
        if oq.calculation_mode in ('event_based_risk',):
            self.add('avglosses_data_transfer')
        if 'exposure' in oq.inputs:
            self.add('exposure_info')
        if 'source_info' in ds:
            self.add('short_source_info')
        if 'performance_data' in ds:
            self.add('performance')
        return self.text

    def save(self, fname):
        """Save the report"""
        with open(fname, 'w') as f:
            f.write(self.text)


def build_report(job_ini, output_dir=None):
    """
    Write a `report.csv` file with information about the calculation
    without running it

    :param job_ini:
        full pathname of the job.ini file
    :param output_dir:
        the directory where the report is written (default the input directory)
    """
    oq = readinput.get_oqparam(job_ini)
    output_dir = output_dir or os.path.dirname(job_ini)
    calc = base.calculators(oq)
    # some taken is care so that the real calculation is not run:
    # the goal is to extract information about the source management only
    calc.SourceManager = source.DummySourceManager
    calc.count_eff_ruptures = (
        lambda result_dict, trt_model:
        result_dict.eff_ruptures.get(trt_model.id, 0))
    with mock.patch.object(
            calc.__class__, 'core_task', source.count_eff_ruptures):
        calc.pre_execute()
    with mock.patch.object(logging.root, 'info'):  # reduce logging
        calc.execute()
    calc.save_params()
    rw = ReportWriter(calc.datastore)
    rw.make_report()
    report = (os.path.join(output_dir, 'report.rst') if output_dir
              else calc.datastore.export_path('report.rst'))
    try:
        rw.save(report)
    except IOError as exc:  # permission error
        sys.stderr.write(str(exc) + '\n')
    return report


def main(directory):
    for cwd, dirs, files in os.walk(directory):
        for f in files:
            if f in ('job.ini', 'job_h.ini', 'job_haz.ini', 'job_hazard.ini'):
                job_ini = os.path.join(cwd, f)
                print(job_ini)
                build_report(job_ini, cwd)

if __name__ == '__main__':
    main(sys.argv[1])
