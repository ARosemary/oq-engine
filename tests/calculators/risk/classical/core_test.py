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

import unittest

from tests.utils import helpers
from tests.calculators.risk import general_test

from openquake.engine import engine
from openquake.engine.calculators.risk.classical import core as classical
from openquake.engine.db import models


class ClassicalRiskCalculatorTestCase(general_test.BaseRiskCalculatorTestCase):
    """
    Integration test for the classical risk calculator
    """
    def setUp(self):
        super(ClassicalRiskCalculatorTestCase, self).setUp()

        self.calculator = classical.ClassicalRiskCalculator(self.job)

    def test_celery_task(self):
        self.calculator.pre_execute()
        self.job.is_running = True
        self.job.status = 'executing'
        self.job.save()

        patch = helpers.patch(
            'openquake.engine.calculators.risk.general.write_loss_curve')

        try:
            mocked_writer = patch.start()

            classical.classical(*self.calculator.task_arg_gen(
                self.calculator.block_size()).next())
        finally:
            patch.stop()

        # we expect 1 asset being filtered out by the region
        # constraint, so there are only two loss curves to be written
        self.assertEqual(2, mocked_writer.call_count)

    def test_complete_workflow(self):
        """
        Test the complete risk classical calculation workflow and test
        for the presence of the outputs
        """
        self.calculator.pre_execute()

        self.job.is_running = True
        self.job.status = 'executing'
        self.job.save()
        self.calculator.execute()

        # 1 loss curve + 3 loss maps + 1 mean + 2 quantile
        self.assertEqual(4,
                         models.Output.objects.filter(oq_job=self.job).count())
        self.assertEqual(1,
                         models.LossCurve.objects.filter(
                             output__oq_job=self.job).count())
        self.assertEqual(2,
                         models.LossCurveData.objects.filter(
                             loss_curve__output__oq_job=self.job).count())
        self.assertEqual(3,
                         models.LossMap.objects.filter(
                             output__oq_job=self.job).count())
        self.assertEqual(6,
                         models.LossMapData.objects.filter(
                             loss_map__output__oq_job=self.job).count())

        files = self.calculator.export(exports=True)
        self.assertEqual(4, len(files))

    def test_hazard_id(self):
        """
        Test that the hazard output used by the calculator is a
        `openquake.engine.db.models.HazardCurve` object
        """

        self.calculator.imt = 'PGA'
        outputs = self.calculator.hazard_outputs(
            self.calculator.rc.get_hazard_calculation())

        self.assertEqual(
            set(["hazard_curve"]), set([o.output_type for o in outputs]))


class PreExecuteTestCase(unittest.TestCase):

    def test_pre_execute_check_imts_raises(self):
        haz_job = engine.prepare_job()
        hazard_curve_output = models.Output.objects.create_output(
            haz_job, 'test_hazard_curve', 'hazard_curve'
        )
        hazard_curve = models.HazardCurve.objects.create(
            output=hazard_curve_output,
            investigation_time=50.0,
            imt='PGV',  # the vulnerability model only defines SA(0.1)
            statistics='mean'
        )

        cfg = helpers.get_data_path('end-to-end-hazard-risk/job_risk.ini')
        risk_job = helpers.get_risk_job(
            cfg, hazard_output_id=hazard_curve_output.id
        )
        calc = classical.ClassicalRiskCalculator(risk_job)

        # Check for compatibility between the IMTs defined in the vulnerability
        # model and the chosen hazard output (--hazard-output-id)
        with self.assertRaises(ValueError) as ar:
            calc.pre_execute()
        self.assertEqual(
            "Vulnerability model and the specified hazard curve are "
            "incompatible. Vulnerability IMT(s): ['SA(0.1)']. Hazard curve "
            "IMT: PGV",
            ar.exception.message
        )

    def test_pre_execute_check_imts_no_errors(self):
        haz_job = engine.prepare_job()
        hazard_curve_output = models.Output.objects.create_output(
            haz_job, 'test_hazard_curve', 'hazard_curve'
        )
        hazard_curve = models.HazardCurve.objects.create(
            output=hazard_curve_output,
            investigation_time=50.0,
            # this imt is compatible with the vuln model
            imt='SA',
            sa_period=0.1,
            sa_damping=5.0,
            statistics='mean'
        )

        cfg = helpers.get_data_path('end-to-end-hazard-risk/job_risk.ini')
        risk_job = helpers.get_risk_job(
            cfg, hazard_output_id=hazard_curve_output.id
        )
        calc = classical.ClassicalRiskCalculator(risk_job)

        # In contrast to the test above (`test_pre_execute_check_imts_raises`),
        # we expect no errors to be raised.
        calc.pre_execute()
