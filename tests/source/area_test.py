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

from nhe.const import TRT
from nhe.scalerel.peer import PeerMSR
from nhe.mfd import TruncatedGRMFD, EvenlyDiscretizedMFD
from nhe.geo import Point, Polygon, NodalPlane
from nhe.pmf import PMF
from nhe.tom import PoissonTOM
from nhe.source.area import AreaSource


class AreaSourceIterRupturesTestCase(unittest.TestCase):
    def make_area_source(self, polygon, discretization, **kwargs):
        default_arguments = {
            'source_id': 'source_id', 'name': 'area source name',
            'tectonic_region_type': TRT.VOLCANIC,
            'mfd': TruncatedGRMFD(a_val=3, b_val=1, min_mag=5,
                                  max_mag=7, bin_width=1),
            'nodal_plane_distribution': PMF([(1, NodalPlane(1, 2, 3))]),
            'hypocenter_distribution': PMF([(1, 4)]),
            'upper_seismogenic_depth': 1.3,
            'lower_seismogenic_depth': 4.9,
            'magnitude_scaling_relationship': PeerMSR(),
            'rupture_aspect_ratio': 1.333,
            'polygon': polygon,
            'area_discretization': discretization,
            'rupture_mesh_spacing': 12.33
        }
        default_arguments.update(kwargs)
        kwargs = default_arguments
        source = AreaSource(**kwargs)
        for key in kwargs:
            self.assertIs(getattr(source, key), kwargs[key])
        return source

    def test_implied_point_sources(self):
        source = self.make_area_source(Polygon([Point(-2, -2), Point(0, -2),
                                                Point(0, 0), Point(-2, 0)]),
                                       discretization=66.7,
                                       rupture_mesh_spacing=5)
        ruptures = list(source.iter_ruptures(PoissonTOM(50)))
        self.assertEqual(len(ruptures), 9 * 2)
        # resulting 3x3 mesh has points in these coordinates:
        lons = [-1.4, -0.8, -0.2]
        lats = [-0.6, -1.2, -1.8]
        ruptures_iter = iter(ruptures)
        for lat in lats:
            for lon in lons:
                r1 = next(ruptures_iter)
                r2 = next(ruptures_iter)
                for rupture in [r1, r2]:
                    self.assertAlmostEqual(rupture.hypocenter.longitude,
                                           lon, delta=1e-3)
                    self.assertAlmostEqual(rupture.hypocenter.latitude,
                                           lat, delta=1e-3)
                    self.assertEqual(rupture.surface.mesh_spacing, 5)
                self.assertEqual(r1.mag, 5.5)
                self.assertEqual(r2.mag, 6.5)
        self.assertEqual(len(ruptures), 9 * 2)

    def test_occurrence_rate_rescaling(self):
        mfd = EvenlyDiscretizedMFD(min_mag=4, bin_width=1,
                                   occurrence_rates=[3])
        polygon = Polygon([Point(0, 0), Point(0, -0.2248),
                           Point(-0.2248, -0.2248), Point(-0.2248, 0)])
        source = self.make_area_source(polygon, discretization=10, mfd=mfd)
        self.assertIs(source.mfd, mfd)
        ruptures = list(source.iter_ruptures(PoissonTOM(1)))
        self.assertEqual(len(ruptures), 4)
        for rupture in ruptures:
            self.assertNotEqual(rupture.occurrence_rate, 3)
            self.assertEqual(rupture.occurrence_rate, 3.0 / 4.0)
