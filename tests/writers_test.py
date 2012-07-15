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


import StringIO
import tempfile
import unittest

from collections import namedtuple

HazardCurveData = namedtuple('HazardCurveData', 'location, poes')
Location = namedtuple('Location', 'x, y')

from nrml import writers


class HazardCurveXMLWriterTestCase(unittest.TestCase):

    FAKE_PATH = 'TODO'  # use a place in /tmp
    TIME = 50.0
    IMLS = [0.005, 0.007, 0.0098]

    def test_validate_metadata_stats_and_smlt_path(self):
        # statistics + smlt path
        metadata = dict(statistics='mean', smlt_path='foo')
        writer = writers.HazardCurveXMLWriter(
            self.FAKE_PATH, self.TIME, 'PGA', self.IMLS, **metadata)
        self.assertRaises(ValueError, writer.validate_metadata)

    def test_validate_metadata_stats_and_gsimlt_path(self):
        # statistics + gsimlt path
        metadata = dict(statistics='mean', gsimlt_path='foo')
        writer = writers.HazardCurveXMLWriter(
            self.FAKE_PATH, self.TIME, 'PGA', self.IMLS, **metadata)
        self.assertRaises(ValueError, writer.validate_metadata)

    def test_validate_metadata_only_smlt_path(self):
        # only 1 logic tree path specified
        metadata = dict(smlt_path='foo')
        writer = writers.HazardCurveXMLWriter(
            self.FAKE_PATH, self.TIME, 'PGA', self.IMLS, **metadata)
        self.assertRaises(ValueError, writer.validate_metadata)

    def test_validate_metadata_only_gsimlt_path(self):
        # only 1 logic tree path specified
        metadata = dict(gsimlt_path='foo')
        writer = writers.HazardCurveXMLWriter(
            self.FAKE_PATH, self.TIME, 'PGA', self.IMLS, **metadata)
        self.assertRaises(ValueError, writer.validate_metadata)

    def test_validate_metadata_invalid_stats(self):
        # invalid stats type
        metadata = dict(statistics='invalid')
        writer = writers.HazardCurveXMLWriter(
            self.FAKE_PATH, self.TIME, 'PGA', self.IMLS, **metadata)
        self.assertRaises(ValueError, writer.validate_metadata)

    def test_validate_metadata_quantile_stats_with_no_value(self):
        # quantile statistics with no quantile value
        metadata = dict(statistics='quantile')
        writer = writers.HazardCurveXMLWriter(
            self.FAKE_PATH, self.TIME, 'PGA', self.IMLS, **metadata)
        self.assertRaises(ValueError, writer.validate_metadata)

    def test_validate_metadata_sa_with_no_period(self):
        # damping but no sa period
        metadata = dict(statistics='mean', sa_damping=5.0)
        writer = writers.HazardCurveXMLWriter(
            self.FAKE_PATH, self.TIME, 'SA', self.IMLS, **metadata)
        self.assertRaises(ValueError, writer.validate_metadata)

    def test_validate_metadata_sa_with_no_damping(self):
        # sa period but no damping
        metadata = dict(statistics='mean', sa_period=5.0)
        writer = writers.HazardCurveXMLWriter(
            self.FAKE_PATH, self.TIME, 'SA', self.IMLS, **metadata)
        self.assertRaises(ValueError, writer.validate_metadata)

    def test_validate_metadata_mean_stats_with_quantile_value(self):
        metadata = dict(statistics='mean', quantile_value=5.0)
        writer = writers.HazardCurveXMLWriter(
            self.FAKE_PATH, self.TIME, 'PGA', self.IMLS, **metadata)
        self.assertRaises(ValueError, writer.validate_metadata)

    def test_validate_metadata_no_stats_with_quantile_value(self):
        metadata = dict(quantile_value=5.0)
        writer = writers.HazardCurveXMLWriter(
            self.FAKE_PATH, self.TIME, 'PGA', self.IMLS, **metadata)
        self.assertRaises(ValueError, writer.validate_metadata)

    def test_serialize(self):
        # Just a basic serialization test.
        expected = StringIO.StringIO("""\
<?xml version='1.0' encoding='UTF-8'?>
<nrml xmlns:gml="http://www.opengis.net/gml" xmlns="http://openquake.org/xmlns/nrml/0.4">
  <hazardCurves IMT="SA" investigationTime="50.0" sourceModelTreePath="b1_b2_b4" gsimTreePath="b1_b4_b5" saPeriod="0.025" saDamping="5.0">
    <IMLs>0.005 0.007 0.0098</IMLs>
    <hazardCurve>
      <gml:Point>
        <gml:pos>38.0 -20.1</gml:pos>
      </gml:Point>
      <poEs>0.1 0.2 0.3</poEs>
    </hazardCurve>
    <hazardCurve>
      <gml:Point>
        <gml:pos>38.1 -20.2</gml:pos>
      </gml:Point>
      <poEs>0.4 0.5 0.6</poEs>
    </hazardCurve>
    <hazardCurve>
      <gml:Point>
        <gml:pos>38.2 -20.3</gml:pos>
      </gml:Point>
      <poEs>0.7 0.8 0.8</poEs>
    </hazardCurve>
  </hazardCurves>
</nrml>
""")

        data = [
            HazardCurveData(location=Location(38.0, -20.1),
                            poes=[0.1, 0.2, 0.3]),
            HazardCurveData(location=Location(38.1, -20.2),
                            poes=[0.4, 0.5, 0.6]),
            HazardCurveData(location=Location(38.2, -20.3),
                            poes=[0.7, 0.8, 0.8]),
        ]
        _, path = tempfile.mkstemp()
        metadata = dict(
            sa_period=0.025, sa_damping=5.0, smlt_path='b1_b2_b4',
            gsimlt_path='b1_b4_b5')
        writer = writers.HazardCurveXMLWriter(
            path, self.TIME, 'SA', self.IMLS, **metadata)
        writer.serialize(data)

        expected_text = expected.readlines()
        fh = open(path, 'r')
        text = fh.readlines()
        print path
        self.assertEqual(expected_text, text)
