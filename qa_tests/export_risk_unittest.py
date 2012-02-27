# Copyright (c) 2010-2012, GEM Foundation.
#
# OpenQuake is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License version 3
# only, as published by the Free Software Foundation.
#
# OpenQuake is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License version 3 for more details
# (a copy is included in the LICENSE file that accompanied this code).
#
# You should have received a copy of the GNU Lesser General Public License
# version 3 along with OpenQuake.  If not, see
# <http://www.gnu.org/licenses/lgpl-3.0.txt> for a copy of the LGPLv3 License.


import shutil
import subprocess
import tempfile
import unittest

from openquake.db import models

from qa_tests._export_test_utils import check_list_calcs
from qa_tests._export_test_utils import check_list_outputs
from tests.utils import helpers


class ExportAggLossCurvesTestCase(unittest.TestCase):
    """Exercises the full end-to-end functionality for running an Event-Based
    Risk calculation and exporting Aggregate Loss curve results from the
    database to file."""

    def test_export_agg_loss_curve(self):
        eb_cfg = helpers.get_data_path(
            'demos/event_based_risk_small/config.gem')
        export_target_dir = tempfile.mkdtemp()

        try:
            ret_code = helpers.run_job(eb_cfg)
            self.assertEqual(0, ret_code)

            calculation = models.OqCalculation.objects.latest('id')
            [output] = models.Output.objects.filter(
                oq_calculation=calculation.id)

            listed_calcs = helpers.prepare_cli_output(subprocess.check_output(
                ['bin/openquake', '--list-calculations']))

            check_list_calcs(self, listed_calcs, calculation.id)

            listed_outputs = helpers.prepare_cli_output(
                subprocess.check_output(
                    ['bin/openquake', '--list-outputs', str(calculation.id)]))

            check_list_outputs(self, listed_outputs, output.id,
                               'agg_loss_curve')
        finally:
            shutil.rmtree(export_target_dir)
