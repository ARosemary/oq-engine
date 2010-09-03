#!/usr/bin/env python
# encoding: utf-8
"""
Test cases for the probablistic scenario described
in the scientific model. The values we check against are taken from
the documentation you can find at <http://to_be_defined>.
"""

import unittest

from opengem.risk.probabilistic_scenario import *
from opengem import shapes

# input test values
ASSET_VALUE = 5.0
INVALID_ASSET_VALUE = 0.0
VULNERABILITY_FUNCTION = shapes.Curve({5.0: 0.0, 6.0: 0.0, 7.0: 0.0, 8.0: 0.0})
HAZARD_CURVE = shapes.Curve({5.0: 0.138, 6.0: 0.099, 7.0: 0.068, 8.0: 0.041})

LOSS_RATIO_EXCEEDANCE_MATRIX = [[0.695, 0.858, 0.990, 1.000], \
        [0.266, 0.510, 0.841, 0.999]]

class ProbabilisticScenarioTestCase(unittest.TestCase):

    # loss curve tests

    def test_empty_loss_curve(self):
        """Degenerate case."""
        
        self.assertEqual(compute_loss_curve(
                shapes.EMPTY_CURVE, ASSET_VALUE),
                shapes.EMPTY_CURVE)
    
    def test_a_loss_curve_is_not_defined_when_the_asset_is_invalid(self):
        self.assertEqual(compute_loss_curve(
                shapes.Curve({0.1: 1.0, 0.2: 2.0, 0.3: 3.0}),
                INVALID_ASSET_VALUE),
                shapes.EMPTY_CURVE)
    
    def test_loss_curve_computation(self):
        loss_ratio_curve = shapes.Curve({0.1: 1.0, 0.2: 2.0, 0.3: 3.0})
        loss_curve = compute_loss_curve(loss_ratio_curve, ASSET_VALUE)

        self.assertEqual(shapes.Curve({0.1 * ASSET_VALUE: 1.0,
                0.2 * ASSET_VALUE: 2.0,
                0.3 * ASSET_VALUE: 3.0}), loss_curve)

    # loss ratio exceedance matrix * po tests
    
    def test_empty_matrix(self):
        """Degenerate case."""
        
        self.assertEqual([], compute_lrem_po(shapes.EMPTY_CURVE,
                [], shapes.EMPTY_CURVE))
        
    def test_lrem_po_computation(self):
        lrem_po = compute_lrem_po(VULNERABILITY_FUNCTION, 
                LOSS_RATIO_EXCEEDANCE_MATRIX, HAZARD_CURVE)

        self.assertAlmostEquals(0.0959, lrem_po[0][0], 0.0001)
        self.assertAlmostEquals(0.0367, lrem_po[1][0], 0.0001)
        self.assertAlmostEquals(0.0849, lrem_po[0][1], 0.0001)
        self.assertAlmostEquals(0.0504, lrem_po[1][1], 0.0001)
        self.assertAlmostEquals(0.0673, lrem_po[0][2], 0.0001)
        self.assertAlmostEquals(0.0571, lrem_po[1][2], 0.0001)
        self.assertAlmostEquals(0.0410, lrem_po[0][3], 0.0001)
        self.assertAlmostEquals(0.0410, lrem_po[1][3], 0.0001)

    # loss ratio curve tests
    
    def test_empty_loss_ratio_curve(self):
        """Degenerate case."""
        
        self.assertEqual(shapes.EMPTY_CURVE, compute_loss_ratio_curve([], []))
        
    def test_loss_ratio_curve_computation(self):
        loss_ratio_curve = compute_loss_ratio_curve([1.0, 2.0], 
                compute_lrem_po(VULNERABILITY_FUNCTION,
                LOSS_RATIO_EXCEEDANCE_MATRIX, HAZARD_CURVE))

        self.assertAlmostEquals(0.2891, loss_ratio_curve.get_for(1.0), 0.0001)
        self.assertAlmostEquals(0.1853, loss_ratio_curve.get_for(2.0), 0.0001)
