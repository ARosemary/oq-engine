# coding=utf-8
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

import numpy
from scipy.interpolate import interp1d
from risklib.range import range_clip


class Curve(object):
    """
    This class defines a curve (discrete function)
    used in the risk domain.
    """

    def __init__(self, pairs):
        """
        Construct a curve from a sequence of tuples.

        The value on the first position of the tuple is the x value,
        the value(s) on the second position is the y value(s).
        """
        pairs = sorted(pairs)  # sort the pairs on x axis
        npairs = len(pairs)
        self.abscissae = numpy.empty(npairs)
        self.ordinates = numpy.empty(npairs)
        for index, (key, val) in enumerate(pairs):
            self.abscissae[index] = key
            self.ordinates[index] = val
        self._interp = None  # set by ordinate_for
        self._inverse = None  # set by abscissa_for

    @property
    def interp(self):
        """Cached attribute. Returns the interpolated function."""
        if self._interp is None:
            self._interp = interp1d(self.abscissae, self.ordinates)
        return self._interp

    @property
    def inverse(self):
        """Cached attribute. Returns the inverse function."""
        if self._inverse is None:
            with_unique_ys = dict(zip(self.ordinates, self.abscissae))
            self._inverse = self.__class__(with_unique_ys.iteritems())
        return self._inverse

    # so that if the idiom ``if curve:`` is possible
    def __nonzero__(self):
        return self.abscissae.size != 0

    # so that the curve is pickeable even if self.interp has been instantiated
    def __getstate__(self):
        return dict(abscissae=self.abscissae, ordinates=self.ordinates,
                    _interp=None, _inverse=self._inverse)

    def __eq__(self, other):
        return numpy.allclose(self.abscissae, other.abscissae)\
            and numpy.allclose(self.ordinates, other.ordinates)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __len__(self):
        return len(self.abscissae)

    def __str__(self):
        return "X Values: %s\nY Values: %s" % (self.abscissae, self.ordinates)

    def rescale_abscissae(self, value):
        """
        Return a new curve with each abscissa value multiplied
        by the value passed as parameter.
        """
        newcurve = Curve(())
        newcurve.abscissae = self.abscissae * value
        newcurve.ordinates = self.ordinates
        return newcurve

    def ordinate_for(self, x_value):
        """
        Return the y value corresponding to the given x value.
        interp1d parameters are a list of abscissae, ordinates.
        This is very useful to speed up the computation and feed
        "directly" numpy.
        """
        return self.interp(range_clip(x_value, self.abscissae))

    def ordinate_diffs(self, xs):
        ys = self.ordinate_for(xs)
        return [i - j for i, j in zip(ys, ys[1:])]

    def abscissa_for(self, y_value):
        """
        Return the x value corresponding to the given y value.
        Notice that non-invertible function are inverted by
        discarding duplicated y values for the same x!
        Mathematicians would cry.
        """
        return self.inverse.ordinate_for(y_value)

    def ordinate_out_of_bounds(self, y_value):
        """
        Check if the given value is outside the Y values boundaries.
        """
        return y_value < min(self.ordinates) or y_value > max(self.ordinates)

EMPTY_CURVE = Curve(())
