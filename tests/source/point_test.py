# nhlib: A New Hazard Library
# Copyright (C) 2012 GEM Foundation
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
import unittest
from decimal import Decimal

from nhlib.const import TRT
from nhlib.source.point import PointSource
from nhlib.source.rupture import ProbabilisticRupture
from nhlib.mfd import TruncatedGRMFD, EvenlyDiscretizedMFD
from nhlib.scalerel.peer import PeerMSR
from nhlib.geo import Point, PlanarSurface, NodalPlane
from nhlib.pmf import PMF
from nhlib.tom import PoissonTOM

from tests.geo.surface import _planar_test_data as planar_surface_test_data


class PointSourceCreationTestCase(unittest.TestCase):
    def make_point_source(self, **kwargs):
        default_arguments = {
            'source_id': 'source_id', 'name': 'source name',
            'tectonic_region_type': TRT.SUBDUCTION_INTRASLAB,
            'mfd': TruncatedGRMFD(a_val=1, b_val=2, min_mag=3,
                                  max_mag=5, bin_width=1),
            'location': Point(1.2, 3.4, 5.6),
            'nodal_plane_distribution': PMF([(1, NodalPlane(1, 2, 3))]),
            'hypocenter_distribution': PMF([(1, 4)]),
            'upper_seismogenic_depth': 1.3,
            'lower_seismogenic_depth': 4.9,
            'magnitude_scaling_relationship': PeerMSR(),
            'rupture_aspect_ratio': 1.333,
            'rupture_mesh_spacing': 1.234
        }
        default_arguments.update(kwargs)
        kwargs = default_arguments
        source = PointSource(**kwargs)
        for key in kwargs:
            self.assertIs(getattr(source, key), kwargs[key])

    def assert_failed_creation(self, exc, msg, **kwargs):
        with self.assertRaises(exc) as ae:
            self.make_point_source(**kwargs)
        self.assertEqual(ae.exception.message, msg)

    def test_wrong_trt(self):
        self.assert_failed_creation(ValueError,
            "unknown tectonic region type 'Sand'",
            tectonic_region_type='Sand'
        )

    def test_negative_upper_seismogenic_depth(self):
        self.assert_failed_creation(ValueError,
            'upper seismogenic depth must be non-negative',
            upper_seismogenic_depth=-0.1
        )

    def test_non_positive_rupture_mesh_spacing(self):
        msg = 'rupture mesh spacing must be positive'
        self.assert_failed_creation(ValueError, msg, rupture_mesh_spacing=-0.1)
        self.assert_failed_creation(ValueError, msg, rupture_mesh_spacing=0)

    def test_lower_depth_above_upper_depth(self):
        self.assert_failed_creation(ValueError,
            'lower seismogenic depth must be below upper seismogenic depth',
            upper_seismogenic_depth=10, lower_seismogenic_depth=8
        )

    def test_lower_depth_equal_to_upper_depth(self):
        self.assert_failed_creation(ValueError,
            'lower seismogenic depth must be below upper seismogenic depth',
            upper_seismogenic_depth=10, lower_seismogenic_depth=10
        )

    def test_hypocenter_depth_out_of_seismogenic_layer(self):
        self.assert_failed_creation(ValueError,
            'depths of all hypocenters must be in between '
            'lower and upper seismogenic depths',
            upper_seismogenic_depth=3, lower_seismogenic_depth=8,
            hypocenter_distribution=PMF([(Decimal('0.3'), 4),
                                         (Decimal('0.7'), 8.001)])
        )

    def test_negative_aspect_ratio(self):
        self.assert_failed_creation(ValueError,
            'rupture aspect ratio must be positive',
            rupture_aspect_ratio=-1
        )

    def test_zero_aspect_ratio(self):
        self.assert_failed_creation(ValueError,
            'rupture aspect ratio must be positive',
            rupture_aspect_ratio=0
        )

    def test_successfull_creation(self):
        self.make_point_source()


class PointSourceIterRupturesTestCase(unittest.TestCase):
    def _get_rupture(self, min_mag, max_mag, hypocenter_depth,
                     aspect_ratio, dip, rupture_mesh_spacing):
        source_id = name = 'test-source'
        trt = TRT.ACTIVE_SHALLOW_CRUST
        mfd = TruncatedGRMFD(a_val=2, b_val=1, min_mag=min_mag,
                             max_mag=max_mag, bin_width=1)
        location = Point(0, 0)
        nodal_plane = NodalPlane(strike=45, dip=dip, rake=-123.23)
        nodal_plane_distribution = PMF([(1, nodal_plane)])
        hypocenter_distribution = PMF([(1, hypocenter_depth)])
        upper_seismogenic_depth = 2
        lower_seismogenic_depth = 16
        magnitude_scaling_relationship = PeerMSR()
        rupture_aspect_ratio = aspect_ratio
        point_source = PointSource(
            source_id, name, trt, mfd, rupture_mesh_spacing,
            magnitude_scaling_relationship, rupture_aspect_ratio,
            upper_seismogenic_depth, lower_seismogenic_depth,
            location, nodal_plane_distribution, hypocenter_distribution
        )
        tom = PoissonTOM(time_span=50)
        ruptures = list(point_source.iter_ruptures(tom))
        self.assertEqual(len(ruptures), 1)
        [rupture] = ruptures
        self.assertIs(rupture.temporal_occurrence_model, tom)
        self.assertIs(rupture.tectonic_region_type, trt)
        self.assertEqual(rupture.rake, nodal_plane.rake)
        self.assertIsInstance(rupture.surface, PlanarSurface)
        self.assertEqual(rupture.surface.mesh_spacing, rupture_mesh_spacing)
        return rupture

    def _check_dimensions(self, surface, length, width, delta=1e-3):
        length_top = surface.top_left.distance(surface.top_right)
        length_bottom = surface.bottom_left.distance(surface.bottom_right)
        self.assertAlmostEqual(length_top, length_bottom, delta=delta)
        self.assertAlmostEqual(length_top, length, delta=delta)

        width_left = surface.top_left.distance(surface.bottom_left)
        width_right = surface.top_right.distance(surface.bottom_right)
        self.assertAlmostEqual(width_left, width_right, delta=delta)
        self.assertAlmostEqual(width_right, width, delta=delta)
        self.assertAlmostEqual(width, surface.width, delta=delta)
        self.assertAlmostEqual(length, surface.length, delta=delta)

    def test_1_rupture_is_inside(self):
        rupture = self._get_rupture(min_mag=5, max_mag=6, hypocenter_depth=8,
                                    aspect_ratio=1, dip=30,
                                    rupture_mesh_spacing=1)
        self.assertEqual(rupture.mag, 5.5)
        self.assertEqual(rupture.hypocenter, Point(0, 0, 8))
        self.assertAlmostEqual(rupture.occurrence_rate, 0.0009)

        surface = rupture.surface
        self._check_dimensions(surface, 5.623413252, 5.623413252)
        self.assertAlmostEqual(0, surface.top_left.distance(Point(
            -0.0333647435005, -0.00239548066924, 6.59414668702
        )), places=5)
        self.assertAlmostEqual(0, surface.top_right.distance(Point(
            0.00239548107539, 0.0333647434713, 6.59414668702
        )), places=5)
        self.assertAlmostEqual(0, surface.bottom_left.distance(Point(
            -0.00239548107539, -0.0333647434713, 9.40585331298
        )), places=5)
        self.assertAlmostEqual(0, surface.bottom_right.distance(Point(
            0.0333647435005, 0.00239548066924, 9.40585331298
        )), places=5)

    def test_2_rupture_shallower_than_upper_seismogenic_depth(self):
        rupture = self._get_rupture(min_mag=5, max_mag=6, hypocenter_depth=3,
                                    aspect_ratio=1, dip=30,
                                    rupture_mesh_spacing=10)
        self.assertEqual(rupture.mag, 5.5)
        self.assertEqual(rupture.hypocenter, Point(0, 0, 3))
        self.assertAlmostEqual(rupture.occurrence_rate, 0.0009)

        surface = rupture.surface
        self._check_dimensions(surface, 5.623413252, 5.623413252)
        self.assertAlmostEqual(0, surface.top_left.distance(Point(
            -0.0288945127134, -0.0068657114195, 2.0
        )), places=5)
        self.assertAlmostEqual(0, surface.top_right.distance(Point(
            0.00686571229256, 0.028894512506, 2.0
        )), places=5)
        self.assertAlmostEqual(0, surface.bottom_left.distance(Point(
            0.00207475040284, -0.0378349743787, 4.81170662595
        )), places=5)
        self.assertAlmostEqual(0, surface.bottom_right.distance(Point(
            0.0378349744035, -0.00207474995049, 4.81170662595
        )), places=5)

    def test_3_rupture_deeper_than_lower_seismogenic_depth(self):
        rupture = self._get_rupture(min_mag=5, max_mag=6, hypocenter_depth=15,
                                    aspect_ratio=1, dip=30,
                                    rupture_mesh_spacing=10)
        self.assertEqual(rupture.hypocenter, Point(0, 0, 15))

        surface = rupture.surface
        self._check_dimensions(surface, 5.623413252, 5.623413252)
        self.assertAlmostEqual(0, surface.top_left.distance(Point(
            -0.0378349744035, 0.00207474995049, 13.188293374
        )), places=5)
        self.assertAlmostEqual(0, surface.top_right.distance(Point(
            -0.00207475040284, 0.0378349743787, 13.188293374
        )), places=5)
        self.assertAlmostEqual(0, surface.bottom_left.distance(Point(
            -0.00686571229256, -0.028894512506, 16.0
        )), places=5)
        self.assertAlmostEqual(0, surface.bottom_right.distance(Point(
            0.0288945127134, 0.0068657114195, 16.0
        )), places=5)

    def test_4_rupture_wider_than_seismogenic_layer(self):
        rupture = self._get_rupture(min_mag=7, max_mag=8, hypocenter_depth=9,
                                    aspect_ratio=1, dip=30,
                                    rupture_mesh_spacing=10)
        self.assertEqual(rupture.mag, 7.5)
        self.assertEqual(rupture.hypocenter, Point(0, 0, 9))

        surface = rupture.surface
        # in this test we need to increase the tolerance because the rupture
        # created is rather big and float imprecision starts to be noticeable
        self._check_dimensions(surface, 112.93848786315641, 28, delta=2e-3)

        self.assertAlmostEqual(0, surface.top_left.distance(Point(
            -0.436201680751, -0.281993828512, 2.0
        )), delta=0.003)  # actual to expected distance is 296 cm
        self.assertAlmostEqual(0, surface.top_right.distance(Point(
            0.282002000777, 0.43619639753, 2.0
        )), delta=0.003)  # 52 cm
        self.assertAlmostEqual(0, surface.bottom_left.distance(Point(
            -0.282002000777, -0.43619639753, 16.0
        )), delta=0.003)  # 133 cm
        self.assertAlmostEqual(0, surface.bottom_right.distance(Point(
            0.436201680751, 0.281993828512, 16.0
        )), delta=0.003)  # 23 cm

    def test_5_vertical_rupture(self):
        rupture = self._get_rupture(min_mag=5, max_mag=6, hypocenter_depth=9,
                                    aspect_ratio=2, dip=90,
                                    rupture_mesh_spacing=4)
        self.assertEqual(rupture.hypocenter, Point(0, 0, 9))

        surface = rupture.surface
        self._check_dimensions(surface, 7.9527072876705063, 3.9763536438352536)

        self.assertAlmostEqual(0, surface.top_left.distance(Point(
            -0.0252862987308, -0.0252862962683, 7.01182317808
        )), places=5)
        self.assertAlmostEqual(0, surface.top_right.distance(Point(
            0.0252862987308, 0.0252862962683, 7.01182317808
        )), places=5)
        self.assertAlmostEqual(0, surface.bottom_left.distance(Point(
            -0.0252862987308, -0.0252862962683, 10.9881768219
        )), places=5)
        self.assertAlmostEqual(0, surface.bottom_right.distance(Point(
            0.0252862987308, 0.0252862962683, 10.9881768219
        )), places=5)

    def test_7_many_ruptures(self):
        source_id = name = 'test7-source'
        trt = TRT.VOLCANIC
        mag1 = 4.5
        mag2 = 5.5
        mag1_rate = 9e-3
        mag2_rate = 9e-4
        hypocenter1 = 9.0
        hypocenter2 = 10.0
        hypocenter1_weight = Decimal('0.8')
        hypocenter2_weight = Decimal('0.2')
        nodalplane1 = NodalPlane(strike=45, dip=90, rake=0)
        nodalplane2 = NodalPlane(strike=0, dip=45, rake=10)
        nodalplane1_weight = Decimal('0.3')
        nodalplane2_weight = Decimal('0.7')
        upper_seismogenic_depth = 2
        lower_seismogenic_depth = 16
        rupture_aspect_ratio = 2
        rupture_mesh_spacing = 0.5
        location = Point(0, 0)
        magnitude_scaling_relationship = PeerMSR()
        tom = PoissonTOM(time_span=50)

        mfd = EvenlyDiscretizedMFD(min_mag=mag1, bin_width=(mag2 - mag1),
                                   occurrence_rates=[mag1_rate, mag2_rate])
        nodal_plane_distribution = PMF([(nodalplane1_weight, nodalplane1),
                                        (nodalplane2_weight, nodalplane2)])
        hypocenter_distribution = PMF([(hypocenter1_weight, hypocenter1),
                                       (hypocenter2_weight, hypocenter2)])
        point_source = PointSource(
            source_id, name, trt, mfd, rupture_mesh_spacing,
            magnitude_scaling_relationship, rupture_aspect_ratio,
            upper_seismogenic_depth, lower_seismogenic_depth,
            location, nodal_plane_distribution, hypocenter_distribution
        )
        actual_ruptures = list(point_source.iter_ruptures(tom))
        self.assertEqual(len(actual_ruptures), 8)
        expected_ruptures = {
            (mag1, nodalplane1.rake, hypocenter1): (
                # probabilistic rupture's occurrence rate
                9e-3 * 0.3 * 0.8,
                # rupture surface corners
                planar_surface_test_data.TEST_7_RUPTURE_1_CORNERS
            ),
            (mag2, nodalplane1.rake, hypocenter1): (
                9e-4 * 0.3 * 0.8,
                planar_surface_test_data.TEST_7_RUPTURE_2_CORNERS
            ),
            (mag1, nodalplane2.rake, hypocenter1): (
                9e-3 * 0.7 * 0.8,
                planar_surface_test_data.TEST_7_RUPTURE_3_CORNERS
            ),
            (mag2, nodalplane2.rake, hypocenter1): (
                9e-4 * 0.7 * 0.8,
                planar_surface_test_data.TEST_7_RUPTURE_4_CORNERS
            ),
            (mag1, nodalplane1.rake, hypocenter2): (
                9e-3 * 0.3 * 0.2,
                planar_surface_test_data.TEST_7_RUPTURE_5_CORNERS
            ),
            (mag2, nodalplane1.rake, hypocenter2): (
                9e-4 * 0.3 * 0.2,
                planar_surface_test_data.TEST_7_RUPTURE_6_CORNERS
            ),
            (mag1, nodalplane2.rake, hypocenter2): (
                9e-3 * 0.7 * 0.2,
                planar_surface_test_data.TEST_7_RUPTURE_7_CORNERS
            ),
            (mag2, nodalplane2.rake, hypocenter2): (
                9e-4 * 0.7 * 0.2,
                planar_surface_test_data.TEST_7_RUPTURE_8_CORNERS
            )
        }
        for actual_rupture in actual_ruptures:
            expected_occurrence_rate, expected_corners = expected_ruptures[
                (actual_rupture.mag, actual_rupture.rake,
                 actual_rupture.hypocenter.depth)
            ]
            self.assertTrue(isinstance(actual_rupture, ProbabilisticRupture))
            self.assertEqual(actual_rupture.occurrence_rate,
                             expected_occurrence_rate)
            self.assertIs(actual_rupture.temporal_occurrence_model, tom)
            self.assertEqual(actual_rupture.tectonic_region_type, trt)
            surface = actual_rupture.surface

            tl, tr, br, bl = expected_corners
            self.assertEqual(tl, surface.top_left)
            self.assertEqual(tr, surface.top_right)
            self.assertEqual(bl, surface.bottom_left)
            self.assertEqual(br, surface.bottom_right)
