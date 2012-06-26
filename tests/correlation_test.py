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

import numpy

from nhlib.imt import SA
from nhlib.correlation import JB2009CorrelationModel
from nhlib.site import Site, SiteCollection
from nhlib.geo import Point


class JB2009CorrelationMatrixTestCase(unittest.TestCase):
    SITECOL = SiteCollection([Site(Point(2, -40), 1, True, 1, 1),
                              Site(Point(2, -40.1), 1, True, 1, 1),
                              Site(Point(2, -40), 1, True, 1, 1),
                              Site(Point(2, -39.9), 1, True, 1, 1)])
    aaae = lambda self, *args, **kwargs: \
        numpy.testing.assert_array_almost_equal(*args, **kwargs)

    def test_no_clustering(self):
        cormo = JB2009CorrelationModel(vs30_clustering=False)
        imt = SA(period=0.1, damping=5)
        corma = cormo.get_correlation_matrix(self.SITECOL, imt)
        self.aaae(corma, [[1,          0.03823366, 1,          0.03823366],
                          [0.03823366, 1,          0.03823366, 0.00146181],
                          [1,          0.03823366, 1,          0.03823366],
                          [0.03823366, 0.00146181, 0.03823366, 1]])

        imt = SA(period=0.95, damping=5)
        corma = cormo.get_correlation_matrix(self.SITECOL, imt)
        self.aaae(corma, [[1,          0.26107857, 1,          0.26107857],
                          [0.26107857, 1,          0.26107857, 0.06816202],
                          [1,          0.26107857, 1,          0.26107857],
                          [0.26107857, 0.06816202, 0.26107857, 1]])

    def test_clustered(self):
        cormo = JB2009CorrelationModel(vs30_clustering=True)
        imt = SA(period=0.001, damping=5)
        corma = cormo.get_correlation_matrix(self.SITECOL, imt)
        self.aaae(corma, [[1,          0.44046654, 1,          0.44046654],
                          [0.44046654, 1,          0.44046654, 0.19401077],
                          [1,          0.44046654, 1,          0.44046654],
                          [0.44046654, 0.19401077, 0.44046654, 1]])

        imt = SA(period=0.5, damping=5)
        corma = cormo.get_correlation_matrix(self.SITECOL, imt)
        self.aaae(corma, [[1,          0.36612758, 1,          0.36612758],
                          [0.36612758, 1,          0.36612758, 0.1340494],
                          [1,          0.36612758, 1,          0.36612758],
                          [0.36612758, 0.1340494, 0.36612758, 1]])

    def test_period_one_and_above(self):
        cormo = JB2009CorrelationModel(vs30_clustering=False)
        cormo2 = JB2009CorrelationModel(vs30_clustering=True)
        imt = SA(period=1.0, damping=5)
        corma = cormo.get_correlation_matrix(self.SITECOL, imt)
        self.aaae(corma, [[1,         0.2730787, 1,          0.2730787],
                          [0.2730787, 1,          0.2730787, 0.07457198],
                          [1,         0.2730787, 1,          0.2730787],
                          [0.2730787, 0.07457198, 0.2730787, 1]])
        corma2 = cormo2.get_correlation_matrix(self.SITECOL, imt)
        self.assertTrue((corma == corma2).all())

        imt = SA(period=10.0, damping=5)
        corma = cormo.get_correlation_matrix(self.SITECOL, imt)
        self.aaae(corma, [[1,          0.56813402, 1,          0.56813402],
                          [0.56813402, 1,          0.56813402, 0.32277627],
                          [1,          0.56813402, 1,          0.56813402],
                          [0.56813402, 0.32277627, 0.56813402, 1]])
        corma2 = cormo2.get_correlation_matrix(self.SITECOL, imt)
        self.assertTrue((corma == corma2).all())
