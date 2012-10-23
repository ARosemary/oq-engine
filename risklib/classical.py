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

from math import exp
from scipy import sqrt, log, stats
from numpy import array, empty, concatenate, linspace, subtract

from risklib.curve import Curve
from risklib.vulnerability_function import _mean_imls


def _loss_ratio_exceedance_matrix(vuln_function, steps):
    """Compute the LREM (Loss Ratio Exceedance Matrix).

    :param vuln_function:
        The vulnerability function used to compute the LREM.
    :type vuln_function:
        :class:`openquake.shapes.VulnerabilityFunction`
    :param int steps:
        Number of steps between loss ratios.
    """
    loss_ratios = _loss_ratios(vuln_function, steps)

    # LREM has number of rows equal to the number of loss ratios
    # and number of columns equal to the number if imls
    lrem = empty((loss_ratios.size, vuln_function.imls.size), float)

    for col, _ in enumerate(vuln_function):
        for row, loss_ratio in enumerate(loss_ratios):
            mean_loss_ratio = vuln_function.loss_ratios[col]
            loss_ratio_stddev = vuln_function.stddevs[col]

            if vuln_function.distribution == "BT":
                lrem[row][col] = stats.beta.sf(loss_ratio,
                    _alpha_value(mean_loss_ratio, loss_ratio_stddev),
                    _beta_value(mean_loss_ratio, loss_ratio_stddev))
            elif vuln_function.distribution == "LN":
                variance = loss_ratio_stddev ** 2.0
                sigma = sqrt(log((variance / mean_loss_ratio ** 2.0) + 1.0))
                mu = exp(log(mean_loss_ratio ** 2.0 /
                     sqrt(variance + mean_loss_ratio ** 2.0)))

                lrem[row][col] = stats.lognorm.sf(loss_ratio, sigma, scale=mu)
            else:
                raise RuntimeError(
                    "Only beta or lognormal distributions are supported")

    return lrem


def _conditional_losses(curve, probabilities):
    return dict([(poe, _conditional_loss(curve, poe))
                 for poe in probabilities])


def _loss_curve(loss_ratio_curve, asset):
    """
    Compute the loss curve for the given asset value.

    A loss curve is obtained from a loss ratio curve by
    multiplying each X value (loss ratio) for the given asset value.
    """

    return loss_ratio_curve.rescale_abscissae(asset)


def _alpha_value(mean_loss_ratio, stddev):
    """
    Compute alpha value

    :param mean_loss_ratio: current loss ratio
    :type mean_loss_ratio: float

    :param stdev: current standard deviation
    :type stdev: float


    :returns: computed alpha value
    """

    return (((1 - mean_loss_ratio) / stddev ** 2 - 1 / mean_loss_ratio) *
            mean_loss_ratio ** 2)


def _beta_value(mean_loss_ratio, stddev):
    """
    Compute beta value

    :param mean_loss_ratio: current loss ratio
    :type mean_loss_ratio: float

    :param stdev: current standard deviation
    :type stdev: float


    :returns: computed beta value
    """
    return (((1 - mean_loss_ratio) / stddev ** 2 - 1 / mean_loss_ratio) *
            (mean_loss_ratio - mean_loss_ratio ** 2))


def _conditional_loss(curve, probability):
    """
    Return the loss (or loss ratio) corresponding to the given
    PoE (Probability of Exceendance).

    Return the max loss (or loss ratio) if the given PoE is smaller
    than the lowest PoE defined.

    Return zero if the given PoE is greater than the
    highest PoE defined.
    """
    loss_curve = curve.with_unique_ordinates()

    if loss_curve.ordinate_out_of_bounds(probability):
        if probability < loss_curve.y_values[-1]:
            return loss_curve.x_values[-1]
        else:
            return 0.0

    return loss_curve.abscissa_for(probability)


def _loss_ratio_curve(vuln_function, lrem, hazard_curve_values, steps):
    """Compute a loss ratio curve for a specific hazard curve (e.g., site),
    by applying a given vulnerability function.

    A loss ratio curve is a function that has loss ratios as X values
    and PoEs (Probabilities of Exceendance) as Y values.

    This is the main (and only) public function of this module.

    :param vuln_function: the vulnerability function used
        to compute the curve.
    :type vuln_function: :py:class:`openquake.shapes.VulnerabilityFunction`
    :param hazard_curve_values: the hazard curve used to compute the curve.
    :type hazard_curve_values: an association list with the
    imls/values of the hazard curve
    :param int steps:
        Number of steps between loss ratios.
    """

    lrem_po = _loss_ratio_exceedance_matrix_per_poos(
        vuln_function, lrem, hazard_curve_values)
    loss_ratios = _loss_ratios(vuln_function, steps)

    return Curve(zip(loss_ratios, lrem_po.sum(axis=1)))


def _loss_ratio_exceedance_matrix_per_poos(
        vuln_function, lrem, hazard_curve_values):
    """Compute the LREM * PoOs (Probability of Occurence) matrix.

    :param vuln_function: the vulnerability function used
        to compute the matrix.
    :type vuln_function: :py:class:`openquake.shapes.VulnerabilityFunction`
    :param hazard_curve: the hazard curve used to compute the matrix.
    :type hazard_curve_values: an association list with the hazard
    curve imls/values
    :param lrem: the LREM used to compute the matrix.
    :type lrem: 2-dimensional :py:class:`numpy.ndarray`
    """

    lrem = array(lrem)
    lrem_po = empty(lrem.shape)
    imls = _mean_imls(vuln_function)

    if hazard_curve_values:
        pos = _poos(hazard_curve_values, imls)
        for idx, po in enumerate(pos):
            lrem_po[:, idx] = lrem[:, idx] * po

    return lrem_po


def _loss_ratios(vuln_function, steps):
    """Generate the set of loss ratios used to compute the LREM
    (Loss Ratio Exceedance Matrix).

    :param vuln_function:
        The vulnerability function where the loss ratios are taken from.
    :type vuln_function:
        :class:`openquake.shapes.VulnerabilityFunction`
    :param int steps:
        Number of steps between loss ratios.
    """

    # we manually add 0.0 as first loss ratio and 1.0 as last loss ratio
    loss_ratios = concatenate(
        (array([0.0]), vuln_function.loss_ratios, array([1.0])))

    return _evenly_spaced_loss_ratios(loss_ratios, steps)


def _evenly_spaced_loss_ratios(loss_ratios, steps):
    """
    Split the loss ratios, producing a new set of loss ratios.

    :param loss_ratios: the loss ratios to split.
    :type loss_ratios: list of floats
    :param steps: the number of steps we make to go from one loss
        ratio to the next. For example, if we have [1.0, 2.0]:

        steps = 1 produces [1.0, 2.0]
        steps = 2 produces [1.0, 1.5, 2.0]
        steps = 3 produces [1.0, 1.33, 1.66, 2.0]
    :type steps: integer
    """

    return (concatenate([concatenate([linspace(x, y, num=steps + 1)[:-1]
        for x, y in zip(loss_ratios, loss_ratios[1:])]), [loss_ratios[-1]]]))


def _poos(hazard_curve_values, imls):
    """
    For each IML (Intensity Measure Level) compute the
    PoOs (Probability of Occurence) from the PoEs
    (Probability of Exceendance) defined in the given hazard curve.

    :param hazard_curve_values: the hazard curve used to compute the PoOs.
    :type hazard_curve_values: an association list with imls and poes
    :param imls: the IMLs (Intensity Measure Level) of the
        vulnerability function used to interpolate the hazard curve.
    :type imls: list of floats
    """

    hazard_curve = Curve(hazard_curve_values)
    poes = hazard_curve.ordinate_for(imls)
    return [subtract(x, y) for x, y in zip(poes, poes[1:])]
