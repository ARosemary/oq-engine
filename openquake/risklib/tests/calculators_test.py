# -*- coding: utf-8 -*-

# Copyright (c) 2013-2014, GEM Foundation.
#
# OpenQuake Risklib is free software: you can redistribute it and/or
# modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of
# the License, or (at your option) any later version.
#
# OpenQuake Risklib is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public
# License along with OpenQuake Risklib. If not, see
# <http://www.gnu.org/licenses/>.


import mock
import unittest
import numpy
import itertools
from openquake.risklib import VulnerabilityFunction
from openquake.risklib import calculators


class ClassicalLossCurveTest(unittest.TestCase):
    def setUp(self):
        vf = VulnerabilityFunction([0.4, 0.7], [0.1, 0.9])
        self.calc = calculators.ClassicalLossCurve(vf, steps=3)
        self.hazard_imls = numpy.linspace(0, 1, 10)

    def test_generator(self):
        vf = mock.Mock()
        steps = mock.Mock()
        with mock.patch('openquake.risklib.scientific.classical') as m:
            calc = calculators.ClassicalLossCurve(vf, steps)
            calc([1, 2, 3])

            self.assertEqual([((vf, 1), {'steps': steps}),
                              ((vf, 2), {'steps': steps}),
                              ((vf, 3), {'steps': steps})], m.call_args_list)

    def test_one_hazard_curve(self):
        hazard_curve = zip(self.hazard_imls, numpy.linspace(1, 0, 10))
        ((losses, poes),) = self.calc([hazard_curve])
        numpy.testing.assert_almost_equal(
            [0., 0.03333333, 0.06666667, 0.1, 0.36666667,
             0.63333333, 0.9, 0.93333333, 0.96666667, 1.], losses)
        numpy.testing.assert_almost_equal(
            [0.6, 0.6, 0.6, 0.6, 0.3, 0.3, 0.3, 0., 0., 0.], poes)

    def test_no_hazard_curves(self):
        loss_curves = self.calc([])

        self.assertFalse(loss_curves)

    def test_multi_hazard_curves(self):
        hazard_curve1 = zip(self.hazard_imls, numpy.linspace(1, 0, 10))
        hazard_curve2 = zip(self.hazard_imls, numpy.linspace(1, 0.1, 10))
        (losses1, poes1), (losses2, poes2) = self.calc(
            [hazard_curve1, hazard_curve2])

        numpy.testing.assert_almost_equal(
            numpy.array([0., 0.03333333, 0.06666667, 0.1, 0.36666667,
                         0.63333333, 0.9, 0.93333333, 0.96666667, 1.]),
            losses1)

        # losses are equal because hazard imls are equal
        numpy.testing.assert_almost_equal(losses1, losses2)

        numpy.testing.assert_almost_equal(
            [0.6, 0.6, 0.6, 0.6, 0.3, 0.3, 0.3, 0., 0., 0.], poes1)

        numpy.testing.assert_almost_equal(
            [0.54, 0.54, 0.54, 0.54, 0.27, 0.27, 0.27, 0., 0., 0.], poes2)


class EventBasedLossCurveTest(unittest.TestCase):
    def setUp(self):
        self.resolution = 5
        self.calc = calculators.EventBasedLossCurve(1, 10, self.resolution)

    def test_generator(self):
        resolution = mock.Mock()
        time_span = mock.Mock()
        tses = mock.Mock()

        with mock.patch('openquake.risklib.scientific.event_based') as m:
            calc = calculators.EventBasedLossCurve(time_span, tses, resolution)
            calc([1, 2, 3])

            self.assertEqual([((1,), dict(curve_resolution=resolution,
                                          time_span=time_span,
                                          tses=tses)),
                              ((2,), dict(curve_resolution=resolution,
                                          time_span=time_span,
                                          tses=tses)),
                              ((3,), dict(curve_resolution=resolution,
                                          time_span=time_span,
                                          tses=tses))], m.call_args_list)

    def test_one_array_of_losses(self):
        losses = numpy.linspace(0, 1, 1000)
        ((losses, poes),) = self.calc([losses])
        numpy.testing.assert_almost_equal(
            numpy.linspace(0, 1, self.resolution), losses)

        numpy.testing.assert_almost_equal([1, 1, 1, 1, 0], poes)

    def test_no_losses(self):
        loss_curves = self.calc([])

        self.assertFalse(loss_curves)

    def test_multi_losses(self):
        set1 = numpy.linspace(0, 0.5, 1000)
        set2 = numpy.linspace(0.5, 1, 1000)
        (losses1, poes1), (losses2, poes2) = self.calc([set1, set2])

        numpy.testing.assert_almost_equal(
            numpy.linspace(0, 0.5, self.resolution),
            losses1)

        numpy.testing.assert_almost_equal(
            numpy.linspace(0, 1, self.resolution),
            losses2)

        numpy.testing.assert_almost_equal([1, 1, 1, 1, 0], poes1)

        numpy.testing.assert_almost_equal([1, 1, 1, 1, 0], poes2)


class LossMapTest(unittest.TestCase):
    def setUp(self):
        losses = numpy.linspace(0, 10, 11)
        poes = numpy.linspace(1, 0, 11)
        self.curves = [(losses, poes), (losses * 2, poes)]

    def test_no_poes(self):
        self.assertEqual(0, calculators.LossMap([])(self.curves).size)

    def test_one_poe(self):
        numpy.testing.assert_allclose(
            [[3.5, 7]], calculators.LossMap([0.65])(self.curves))

    def test_more_poes(self):
        numpy.testing.assert_allclose(
            [[4.5, 9], [5, 10]],
            calculators.LossMap([0.55, 0.5])(self.curves))


class AssetStatisticsTestCase(unittest.TestCase):
    BASE_EXPECTED_POES = numpy.linspace(1, 0, 11)

    def setUp(self):
        self.losses = numpy.linspace(0, 1, 11)

    # fake post_processing module singleton
    class post_processing(object):
        @staticmethod
        def mean_curve(_curve_poes, _weights):
            return (AssetStatisticsTestCase.BASE_EXPECTED_POES)

        @staticmethod
        def weighted_quantile_curve(_curve_poes, _weights, quantile):
            return -AssetStatisticsTestCase.BASE_EXPECTED_POES * quantile

        @staticmethod
        def quantile_curve(_curve_poes, quantile):
            return AssetStatisticsTestCase.BASE_EXPECTED_POES * quantile

    def test_compute_stats_no_quantiles_no_poes(self):
        (mean_curve, mean_maps, quantile_curves, quantile_maps) = (
            calculators.asset_statistics(
                self.losses, mock.Mock(), [],
                [None], [], self.post_processing))

        numpy.testing.assert_allclose(mean_curve,
                                      (self.losses, self.BASE_EXPECTED_POES))

        self.assertEqual(0, quantile_curves.size)
        self.assertEqual(0, mean_maps.size)
        self.assertEqual(0, quantile_maps.size)

    def test_compute_stats_quantiles_weighted(self):
        (mean_curve, mean_maps, quantile_curves, quantile_maps) = (
            calculators.asset_statistics(
                self.losses, mock.Mock(),
                quantiles=[0.1, 0.2],
                poes=[],
                weights=[0.1, 0.2],
                post_processing=self.post_processing))

        numpy.testing.assert_allclose(
            mean_curve, (self.losses, self.BASE_EXPECTED_POES))

        q1, q2 = quantile_curves
        numpy.testing.assert_allclose(
            q1, (self.losses, -self.BASE_EXPECTED_POES * 0.1))
        numpy.testing.assert_allclose(
            q2, (self.losses, -self.BASE_EXPECTED_POES * 0.2))

        self.assertEqual(0, mean_maps.size)
        self.assertEqual(0, quantile_maps.size)

    def test_compute_stats_quantiles_montecarlo(self):
        (mean_curve, mean_maps, quantile_curves, quantile_maps) = (
            calculators.asset_statistics(
                self.losses, mock.Mock(),
                quantiles=[0.1, 0.2],
                poes=[],
                weights=[None, None],
                post_processing=self.post_processing))

        numpy.testing.assert_allclose(
            mean_curve, (self.losses, self.BASE_EXPECTED_POES))

        q1, q2 = quantile_curves
        numpy.testing.assert_allclose(
            q1, (self.losses, self.BASE_EXPECTED_POES * 0.1))
        numpy.testing.assert_allclose(
            q2, (self.losses, self.BASE_EXPECTED_POES * 0.2))

        self.assertEqual(0, mean_maps.size)
        self.assertEqual(0, quantile_maps.size)

    def test_compute_stats_quantile_poes(self):
        (mean_curve, mean_map, quantile_curves, quantile_maps) = (
            calculators.asset_statistics(
                self.losses, mock.Mock(),
                quantiles=[0.1, 0.2],
                poes=[0.2, 0.8],
                weights=[None],
                post_processing=self.post_processing))

        numpy.testing.assert_allclose(
            mean_curve, (self.losses, self.BASE_EXPECTED_POES))
        q1, q2 = quantile_curves
        numpy.testing.assert_allclose(
            q1, (self.losses, self.BASE_EXPECTED_POES * 0.1))
        numpy.testing.assert_allclose(
            q2, (self.losses, self.BASE_EXPECTED_POES * 0.2))

        numpy.testing.assert_allclose(mean_map, [0.8, 0.2])

        numpy.testing.assert_allclose(quantile_maps, numpy.zeros((2, 2)))

    def test_exposure(self):
        resolution = 10

        # testing exposure_statistics with arrays of different shapes
        for quantile_nr, poe_nr, asset_nr in itertools.product(
                range(3), range(3), range(1, 4)):
            with mock.patch(
                    'openquake.risklib.calculators.asset_statistics') as m:
                m.return_value = (numpy.empty((2, resolution)),
                                  numpy.empty(poe_nr),
                                  numpy.empty((quantile_nr, 2, resolution)),
                                  numpy.empty((quantile_nr, poe_nr)))

                loss_curves = numpy.empty((asset_nr, 2, resolution))

                (mean_curves, mean_average_losses, mean_maps,
                 quantile_curves, quantile_average_losses, quantile_maps) = (
                    calculators.exposure_statistics(loss_curves,
                                                    numpy.empty(poe_nr),
                                                    numpy.empty(asset_nr),
                                                    numpy.empty(quantile_nr),
                                                    mock.Mock()))

                self.assertEqual((asset_nr, 2, resolution), mean_curves.shape)
                self.assertEqual((asset_nr, ), mean_average_losses.shape)
                self.assertEqual((poe_nr, asset_nr), mean_maps.shape)
                self.assertEqual((quantile_nr, asset_nr, 2, resolution),
                                 quantile_curves.shape)
                self.assertEqual((quantile_nr, asset_nr),
                                 quantile_average_losses.shape)
                self.assertEqual((quantile_nr, poe_nr, asset_nr),
                                 quantile_maps.shape)
