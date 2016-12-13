# -*- coding: utf-8 -*-
# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright (C) 2012-2016 GEM Foundation
#
# OpenQuake is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OpenQuake is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with OpenQuake. If not, see <http://www.gnu.org/licenses/>.

"""
This module includes the scientific API of the oq-risklib
"""
from __future__ import division
import abc
import copy
import bisect
import collections

import numpy
from numpy.testing import assert_equal
from scipy import interpolate, stats, random

from openquake.baselib.general import CallableDict
from openquake.hazardlib.stats import mean_curve, quantile_curve
from openquake.risklib import utils
from openquake.baselib.python3compat import with_metaclass

F32 = numpy.float32
U32 = numpy.uint32


def build_dtypes(curve_resolution, conditional_loss_poes, insured=False):
    """
    Returns loss_curve_dt and loss_maps_dt
    """
    pairs = [('losses', (F32, curve_resolution)),
             ('poes', (F32, curve_resolution)),
             ('avg', F32)]
    if insured:
        pairs += [(name + '_ins', pair) for name, pair in pairs]
    loss_curve_dt = numpy.dtype(pairs)
    lst = [('poe-%s' % poe, F32) for poe in conditional_loss_poes]
    if insured:
        lst += [(name + '_ins', pair) for name, pair in lst]
    loss_maps_dt = numpy.dtype(lst) if lst else None
    return loss_curve_dt, loss_maps_dt


def extract_poe_ins(name):
    """
    >>> extract_poe_ins('poe-0.1')
    (0.1, 0)
    >>> extract_poe_ins('poe-0.2_ins')
    (0.2, 1)
    """
    ins = 0
    if name.endswith('_ins'):
        ins = 1
        name = name[:-4]
    poe = float(name[4:])
    return poe, ins


class Output(object):
    """
    A generic container of attributes. Only assets, loss_type, hid and weight
    are always defined.

    :param assets: a list of assets with the same taxonomy
    :param loss_type: a loss type string
    :param hid: ordinal of the hazard realization (can be None)
    :param weight: weight of the realization (can be None)
    """
    def __init__(self, assets, loss_type, hid=None, weight=0, **attrs):
        self.assets = assets
        self.loss_type = loss_type
        self.hid = hid
        self.weight = weight
        vars(self).update(attrs)

    @property
    def taxonomy(self):
        return self.assets[0].taxonomy

    def __repr__(self):
        return '<%s %s, hid=%s>' % (
            self.__class__.__name__, self.loss_type, self.hid)

    def __str__(self):
        items = '\n'.join('%s=%s' % item for item in vars(self).items())
        return '<%s\n%s>' % (self.__class__.__name__, items)


def fine_graining(points, steps):
    """
    :param points: a list of floats
    :param int steps: expansion steps (>= 2)

    >>> fine_graining([0, 1], steps=0)
    [0, 1]
    >>> fine_graining([0, 1], steps=1)
    [0, 1]
    >>> fine_graining([0, 1], steps=2)
    array([ 0. ,  0.5,  1. ])
    >>> fine_graining([0, 1], steps=3)
    array([ 0.        ,  0.33333333,  0.66666667,  1.        ])
    >>> fine_graining([0, 0.5, 0.7, 1], steps=2)
    array([ 0.  ,  0.25,  0.5 ,  0.6 ,  0.7 ,  0.85,  1.  ])

    N points become S * (N - 1) + 1 points with S > 0
    """
    if steps < 2:
        return points
    ls = numpy.concatenate([numpy.linspace(x, y, num=steps + 1)[:-1]
                            for x, y in utils.pairwise(points)])
    return numpy.concatenate([ls, [points[-1]]])

#
# Input models
#


class VulnerabilityFunction(object):
    dtype = numpy.dtype([('iml', F32), ('loss_ratio', F32), ('cov', F32)])

    def __init__(self, vf_id, imt, imls, mean_loss_ratios, covs=None,
                 distribution="LN"):
        """
        A wrapper around a probabilistic distribution function
        (currently only the log normal distribution is supported).
        It is meant to be pickeable to allow distributed computation.
        The only important method is `.__call__`, which applies
        the vulnerability function to a given set of ground motion
        fields and epsilons and return a loss matrix with N x R
        elements.

        :param str vf_id: Vulnerability Function ID
        :param str imt: Intensity Measure Type as a string

        :param list imls: Intensity Measure Levels for the
            vulnerability function. All values must be >= 0.0, values
            must be arranged in ascending order with no duplicates

        :param list mean_loss_ratios: Mean Loss ratio values, equal in
        length to imls, where value >= 0.

        :param list covs: Coefficients of Variation. Equal in length
        to mean loss ratios. All values must be >= 0.0.

        :param str distribution_name: The probabilistic distribution
            related to this function.
        """
        self.id = vf_id
        self.imt = imt
        self._check_vulnerability_data(
            imls, mean_loss_ratios, covs, distribution)
        self.imls = numpy.array(imls)
        self.mean_loss_ratios = numpy.array(mean_loss_ratios)

        if covs is not None:
            self.covs = numpy.array(covs)
        else:
            self.covs = numpy.zeros(self.imls.shape)

        for lr, cov in zip(self.mean_loss_ratios, self.covs):
            if lr == 0.0 and cov > 0.0:
                msg = ("It is not valid to define a loss ratio = 0.0 with a "
                       "corresponding coeff. of variation > 0.0")
                raise ValueError(msg)

        self.distribution_name = distribution

        # to be set in .init(), called also by __setstate__
        (self.stddevs, self._mlr_i1d, self._covs_i1d,
         self.distribution) = None, None, None, None
        self.init()

    def init(self):
        self.stddevs = self.covs * self.mean_loss_ratios
        self._mlr_i1d = interpolate.interp1d(self.imls, self.mean_loss_ratios)
        self._covs_i1d = interpolate.interp1d(self.imls, self.covs)
        self.set_distribution(None)

    def set_distribution(self, epsilons=None):
        if (self.covs > 0).any():
            self.distribution = DISTRIBUTIONS[self.distribution_name]()
        else:
            self.distribution = DegenerateDistribution()
        self.distribution.epsilons = (numpy.array(epsilons)
                                      if epsilons is not None else None)

    def interpolate(self, gmvs):
        """
        :param gmvs:
           array of intensity measure levels
        :returns:
           (interpolated loss ratios, interpolated covs, indices > min)
        """
        # gmvs are clipped to max(iml)
        gmvs_curve = numpy.piecewise(
            gmvs, [gmvs > self.imls[-1]], [self.imls[-1], lambda x: x])
        idxs = gmvs_curve >= self.imls[0]  # indices over the minimum
        gmvs_curve = gmvs_curve[idxs]
        return self._mlr_i1d(gmvs_curve), self._cov_for(gmvs_curve), idxs

    def sample(self, means, covs, idxs, epsilons):
        """
        Sample the epsilons and apply the corrections to the means.
        This method is called only if there are nonzero covs.

        :param means:
           array of E' loss ratios
        :param covs:
           array of E' floats
        :param idxs:
           array of E booleans with E >= E'
        :param epsilons:
           array of E floats
        :returns:
           array of E' loss ratios
        """
        self.set_distribution(epsilons)
        return self.distribution.sample(means, covs, None, idxs)

    # this is used in the tests, not in the engine code base
    def __call__(self, gmvs, epsilons):
        """
        A small wrapper around .interpolate and .apply_to
        """
        means, covs, idxs = self.interpolate(gmvs)
        # for gmvs < min(iml) we return a loss of 0 (default)
        ratios = numpy.zeros(len(gmvs))
        ratios[idxs] = self.sample(means, covs, idxs, epsilons)
        return ratios

    def strictly_increasing(self):
        """
        :returns:
          a new vulnerability function that is strictly increasing.
          It is built by removing piece of the function where the mean
          loss ratio is constant.
        """
        imls, mlrs, covs = [], [], []

        previous_mlr = None
        for i, mlr in enumerate(self.mean_loss_ratios):
            if previous_mlr == mlr:
                continue
            else:
                mlrs.append(mlr)
                imls.append(self.imls[i])
                covs.append(self.covs[i])
                previous_mlr = mlr

        return self.__class__(
            self.id, self.imt, imls, mlrs, covs, self.distribution_name)

    def mean_loss_ratios_with_steps(self, steps):
        """
        Split the mean loss ratios, producing a new set of loss ratios. The new
        set of loss ratios always includes 0.0 and 1.0

        :param int steps:
            the number of steps we make to go from one loss
            ratio to the next. For example, if we have [0.5, 0.7]::

             steps = 1 produces [0.0,  0.5, 0.7, 1]
             steps = 2 produces [0.0, 0.25, 0.5, 0.6, 0.7, 0.85, 1]
             steps = 3 produces [0.0, 0.17, 0.33, 0.5, 0.57, 0.63,
                                 0.7, 0.8, 0.9, 1]
        """
        loss_ratios = self.mean_loss_ratios

        if min(loss_ratios) > 0.0:
            # prepend with a zero
            loss_ratios = numpy.concatenate([[0.0], loss_ratios])

        if max(loss_ratios) < 1.0:
            # append a 1.0
            loss_ratios = numpy.concatenate([loss_ratios, [1.0]])

        return fine_graining(loss_ratios, steps)

    def _cov_for(self, imls):
        """
        Clip `imls` to the range associated with the support of the
        vulnerability function and returns the corresponding
        covariance values by linear interpolation. For instance
        if the range is [0.005, 0.0269] and the imls are
        [0.0049, 0.006, 0.027], the clipped imls are
        [0.005,  0.006, 0.0269].
        """
        return self._covs_i1d(
            numpy.piecewise(
                imls,
                [imls > self.imls[-1], imls < self.imls[0]],
                [self.imls[-1], self.imls[0], lambda x: x]))

    def __getstate__(self):
        return (self.id, self.imt, self.imls, self.mean_loss_ratios,
                self.covs, self.distribution_name)

    def __setstate__(self, state):
        self.id = state[0]
        self.imt = state[1]
        self.imls = state[2]
        self.mean_loss_ratios = state[3]
        self.covs = state[4]
        self.distribution_name = state[5]
        self.init()

    def _check_vulnerability_data(self, imls, loss_ratios, covs, distribution):
        assert_equal(imls, sorted(set(imls)))
        assert all(x >= 0.0 for x in imls)
        assert covs is None or len(covs) == len(imls)
        assert len(loss_ratios) == len(imls)
        assert all(x >= 0.0 for x in loss_ratios)
        assert covs is None or all(x >= 0.0 for x in covs)
        assert distribution in ["LN", "BT"]

    @utils.memoized
    def loss_ratio_exceedance_matrix(self, steps):
        """Compute the LREM (Loss Ratio Exceedance Matrix).

        :param int steps:
            Number of steps between loss ratios.
        """

        # add steps between mean loss ratio values
        loss_ratios = self.mean_loss_ratios_with_steps(steps)

        # LREM has number of rows equal to the number of loss ratios
        # and number of columns equal to the number of imls
        lrem = numpy.empty((loss_ratios.size, self.imls.size), float)

        for row, loss_ratio in enumerate(loss_ratios):
            for col, (mean_loss_ratio, stddev) in enumerate(
                    zip(self.mean_loss_ratios, self.stddevs)):
                lrem[row][col] = self.distribution.survival(
                    loss_ratio, mean_loss_ratio, stddev)
        return loss_ratios, lrem

    @utils.memoized
    def mean_imls(self):
        """
        Compute the mean IMLs (Intensity Measure Level)
        for the given vulnerability function.

        :param vulnerability_function: the vulnerability function where
            the IMLs (Intensity Measure Level) are taken from.
        :type vuln_function:
           :py:class:`openquake.risklib.vulnerability_function.\
           VulnerabilityFunction`
        """
        return numpy.array(
            [max(0, self.imls[0] - (self.imls[1] - self.imls[0]) / 2.)] +
            [numpy.mean(pair) for pair in utils.pairwise(self.imls)] +
            [self.imls[-1] + (self.imls[-1] - self.imls[-2]) / 2.])

    def __toh5__(self):
        """
        :returns: a pair (array, attrs) suitable for storage in HDF5 format
        """
        array = numpy.zeros(len(self.imls), self.dtype)
        array['iml'] = self.imls
        array['loss_ratio'] = self.mean_loss_ratios
        array['cov'] = self.covs
        return array, {'id': self.id, 'imt': self.imt,
                       'distribution_name': self.distribution_name}

    def __fromh5__(self, array, attrs):
        vars(self).update(attrs)
        self.imls = array['iml']
        self.mean_loss_ratios = array['loss_ratio']
        self.covs = array['cov']

    def __repr__(self):
        return '<VulnerabilityFunction(%s, %s)>' % (self.id, self.imt)


class VulnerabilityFunctionWithPMF(VulnerabilityFunction):
    """
    Vulnerability function with an explicit distribution of probabilities

    :param str vf_id: vulnerability function ID
    :param str imt: Intensity Measure Type
    :param imls: intensity measure levels (L)
    :param ratios: an array of mean ratios (M)
    :param probs: a matrix of probabilities of shape (M, L)
    """
    def __init__(self, vf_id, imt, imls, loss_ratios, probs, seed=42):
        self.id = vf_id
        self.imt = imt
        self._check_vulnerability_data(imls, loss_ratios, probs)
        self.imls = imls
        self.loss_ratios = loss_ratios
        self.probs = probs
        self.seed = seed
        self.distribution_name = "PM"

        # to be set in .init(), called also by __setstate__
        (self._probs_i1d, self.distribution) = None, None
        self.init()

        ls = [('iml', F32)] + [('prob-%s' % lr, F32) for lr in loss_ratios]
        self.dtype = numpy.dtype(ls)

    def init(self):
        self._probs_i1d = interpolate.interp1d(self.imls, self.probs)
        self.set_distribution(None)

    def set_distribution(self, epsilons=None):
        self.distribution = DISTRIBUTIONS[self.distribution_name]()
        self.distribution.epsilons = epsilons
        self.distribution.seed = self.seed

    def __getstate__(self):
        return (self.id, self.imt, self.imls, self.loss_ratios,
                self.probs, self.distribution_name, self.seed)

    def __setstate__(self, state):
        self.id = state[0]
        self.imt = state[1]
        self.imls = state[2]
        self.loss_ratios = state[3]
        self.probs = state[4]
        self.distribution_name = state[5]
        self.seed = state[6]
        self.init()

    def _check_vulnerability_data(self, imls, loss_ratios, probs):
        assert all(x >= 0.0 for x in imls)
        assert all(x >= 0.0 for x in loss_ratios)
        assert all([1.0 >= x >= 0.0 for x in y] for y in probs)
        assert probs.shape[0] == len(loss_ratios)
        assert probs.shape[1] == len(imls)

    def interpolate(self, gmvs):
        """
        :param gmvs:
           array of intensity measure levels
        :returns:
           (interpolated probabilities, None, indices > min)
        """
        # gmvs are clipped to max(iml)
        gmvs_curve = numpy.piecewise(
            gmvs, [gmvs > self.imls[-1]], [self.imls[-1], lambda x: x])
        idxs = gmvs_curve >= self.imls[0]  # indices over the minimum
        gmvs_curve = gmvs_curve[idxs]
        return self._probs_i1d(gmvs_curve), None, idxs

    def sample(self, probs, _covs, idxs, epsilons):
        """
        Sample the epsilons and applies the corrections to the probabilities.
        This method is called only if there are epsilons.

        :param probs:
           array of E' floats
        :param _covs:
           ignored, it is there only for API consistency
        :param idxs:
           array of E booleans with E >= E'
        :param epsilons:
           array of E floats
        :returns:
           array of E' probabilities
        """
        self.set_distribution(epsilons)
        return self.distribution.sample(self.loss_ratios, probs)

    @utils.memoized
    def loss_ratio_exceedance_matrix(self, steps):
        """Compute the LREM (Loss Ratio Exceedance Matrix).
        Required for the Classical Risk and BCR Calculators.
        Currently left unimplemented as the PMF format is used only for the
        Scenario and Event Based Risk Calculators
        :param int steps:
            Number of steps between loss ratios.
        """
        # TODO: to be implemented if the classical risk calculator
        # needs to support the pmf vulnerability format

    def __toh5__(self):
        """
        :returns: a pair (array, attrs) suitable for storage in HDF5 format
        """
        array = numpy.zeros(len(self.imls), self.dtype)
        array['iml'] = self.imls
        for i, lr in enumerate(self.loss_ratios):
            array['prob-%s' % lr] = self.probs[i]
        return array, {'id': self.id, 'imt': self.imt,
                       'distribution_name': self.distribution_name}

    def __fromh5__(self, array, attrs):
        lrs = [n.split('-')[1] for n in array.dtype.names if '-' in n]
        self.loss_ratios = map(float, lrs)
        self.imls = array['iml']
        self.probs = array
        vars(self).update(attrs)

    def __repr__(self):
        return '<VulnerabilityFunctionWithPMF(%s, %s)>' % (self.id, self.imt)


# this is meant to be instantiated by riskmodels.get_risk_models
class VulnerabilityModel(dict):
    """
    Container for a set of vulnerability functions. You can access each
    function given the IMT and taxonomy with the square bracket notation.

    :param str id: ID of the model
    :param str assetCategory: asset category (i.e. buildings, population)
    :param str lossCategory: loss type (i.e. structural, contents, ...)

    All such attributes are None for a vulnerability model coming from a
    NRML 0.4 file.
    """
    def __init__(self, id=None, assetCategory=None, lossCategory=None):
        self.id = id
        self.assetCategory = assetCategory
        self.lossCategory = lossCategory

    def __repr__(self):
        return '<%s %s %s>' % (
            self.__class__.__name__, self.lossCategory, sorted(self))


# ############################## fragility ############################### #

class FragilityFunctionContinuous(object):
    # FIXME (lp). Should be re-factored with LogNormalDistribution
    def __init__(self, limit_state, mean, stddev):
        self.limit_state = limit_state
        self.mean = mean
        self.stddev = stddev

    def __call__(self, iml):
        """
        Compute the Probability of Exceedance (PoE) for the given
        Intensity Measure Level (IML).
        """
        variance = self.stddev ** 2.0
        sigma = numpy.sqrt(numpy.log(
            (variance / self.mean ** 2.0) + 1.0))

        mu = self.mean ** 2.0 / numpy.sqrt(
            variance + self.mean ** 2.0)

        return stats.lognorm.cdf(iml, sigma, scale=mu)

    def __getstate__(self):
        return dict(limit_state=self.limit_state,
                    mean=self.mean, stddev=self.stddev)

    def __repr__(self):
        return '<%s(%s, %s, %s)>' % (
            self.__class__.__name__, self.limit_state, self.mean, self.stddev)


class FragilityFunctionDiscrete(object):

    def __init__(self, limit_state, imls, poes, no_damage_limit=None):
        self.limit_state = limit_state
        self.imls = imls
        self.poes = poes
        self._interp = None
        self.no_damage_limit = no_damage_limit

    @property
    def interp(self):
        if self._interp is not None:
            return self._interp
        self._interp = interpolate.interp1d(self.imls, self.poes)
        return self._interp

    def __call__(self, iml):
        """
        Compute the Probability of Exceedance (PoE) for the given
        Intensity Measure Level (IML).
        """
        highest_iml = self.imls[-1]

        if self.no_damage_limit and iml < self.no_damage_limit:
            return 0.
        # when the intensity measure level is above
        # the range, we use the highest one
        return self.interp(highest_iml if iml > highest_iml else iml)

    # so that the curve is pickeable
    def __getstate__(self):
        return dict(limit_state=self.limit_state,
                    poes=self.poes, imls=self.imls, _interp=None,
                    no_damage_limit=self.no_damage_limit)

    def __eq__(self, other):
        return (self.poes == other.poes and self.imls == other.imls and
                self.no_damage_limit == other.no_damage_limit)

    def __ne__(self, other):
        return not self == other

    def __repr__(self):
        return '<%s(%s, %s, %s)>' % (
            self.__class__.__name__, self.limit_state, self.imls, self.poes)


class FragilityFunctionList(list):
    """
    A list of fragility functions with common attributes; there is a
    function for each limit state.
    """
    def __init__(self, array, **attrs):
        self.array = array
        vars(self).update(attrs)

    def mean_loss_ratios_with_steps(self, steps):
        """For compatibility with vulnerability functions"""
        return fine_graining(self.imls, steps)

    def __toh5__(self):
        return self.array, {k: v for k, v in vars(self).items()
                            if k != 'array' and v is not None}

    def __fromh5__(self, array, attrs):
        self.array = array
        vars(self).update(attrs)

    def __repr__(self):
        kvs = ['%s=%s' % item for item in vars(self).items()]
        return '<FragilityFunctionList %s>' % ', '.join(kvs)


ConsequenceFunction = collections.namedtuple(
    'ConsequenceFunction', 'id dist params')


class ConsequenceModel(dict):
    """
    Container for a set of consequence functions. You can access each
    function given its name with the square bracket notation.

    :param str id: ID of the model
    :param str assetCategory: asset category (i.e. buildings, population)
    :param str lossCategory: loss type (i.e. structural, contents, ...)
    :param str description: description of the model
    :param limitStates: a list of limit state strings
    :param consequence_functions: a dictionary name -> ConsequenceFunction
    """

    def __init__(self, id, assetCategory, lossCategory, description,
                 limitStates):
        self.id = id
        self.assetCategory = assetCategory
        self.lossCategory = lossCategory
        self.description = description
        self.limitStates = limitStates

    def __repr__(self):
        return '<%s %s %s %s>' % (
            self.__class__.__name__, self.lossCategory,
            ', '.join(self.limitStates), ' '.join(sorted(self)))


def build_imls(ff, continuous_fragility_discretization,
               steps_per_interval=0):
    """
    Build intensity measure levels from a fragility function. If the function
    is continuous, they are produced simply as a linear space between minIML
    and maxIML. If the function is discrete, they are generated with a
    complex logic depending on the noDamageLimit and the parameter
    steps per interval.

    :param ff: a fragility function object
    :param continuous_fragility_discretization: .ini file parameter
    :param steps_per_interval:  .ini file parameter
    :returns: generated imls
    """
    if ff.format == 'discrete':
        imls = ff.imls
        if ff.nodamage is not None and ff.nodamage < imls[0]:
            imls = [ff.nodamage] + imls
        if steps_per_interval > 1:
            gen_imls = fine_graining(imls, steps_per_interval)
        else:
            gen_imls = imls
    else:  # continuous
        gen_imls = numpy.linspace(ff.minIML, ff.maxIML,
                                  continuous_fragility_discretization)
    return gen_imls


# this is meant to be instantiated by riskmodels.get_fragility_model
class FragilityModel(dict):
    """
    Container for a set of fragility functions. You can access each
    function given the IMT and taxonomy with the square bracket notation.

    :param str id: ID of the model
    :param str assetCategory: asset category (i.e. buildings, population)
    :param str lossCategory: loss type (i.e. structural, contents, ...)
    :param str description: description of the model
    :param limitStates: a list of limit state strings
    """

    def __init__(self, id, assetCategory, lossCategory, description,
                 limitStates):
        self.id = id
        self.assetCategory = assetCategory
        self.lossCategory = lossCategory
        self.description = description
        self.limitStates = limitStates

    def __repr__(self):
        return '<%s %s %s %s>' % (
            self.__class__.__name__, self.lossCategory,
            self.limitStates, sorted(self))

    def build(self, continuous_fragility_discretization, steps_per_interval):
        """
        Return a new FragilityModel instance, in which the values have been
        replaced with FragilityFunctionList instances.

        :param continuous_fragility_discretization:
            configuration parameter
        :param steps_per_interval:
            configuration parameter
        """
        newfm = copy.copy(self)
        for key, ff in self.items():
            newfm[key] = new = copy.copy(ff)
            # TODO: this is complicated: check with Anirudh
            add_zero = (ff.format == 'discrete' and
                        ff.nodamage is not None and ff.nodamage < ff.imls[0])
            new.imls = build_imls(new, continuous_fragility_discretization)
            if steps_per_interval > 1:
                new.interp_imls = build_imls(  # passed to classical_damage
                    new, continuous_fragility_discretization,
                    steps_per_interval)
            for i, ls in enumerate(self.limitStates):
                data = ff.array[i]
                if ff.format == 'discrete':
                    if add_zero:
                        new.append(FragilityFunctionDiscrete(
                            ls, [ff.nodamage] + ff.imls,
                            numpy.concatenate([[0.], data]),
                            ff.nodamage))
                    else:
                        new.append(FragilityFunctionDiscrete(
                            ls, ff.imls, data, ff.nodamage))
                else:  # continuous
                    new.append(FragilityFunctionContinuous(
                        ls, data['mean'], data['stddev']))
        return newfm


#
# Distribution & Sampling
#

DISTRIBUTIONS = CallableDict()


class Distribution(with_metaclass(abc.ABCMeta)):
    """
    A Distribution class models continuous probability distribution of
    random variables used to sample losses of a set of assets. It is
    usually registered with a name (e.g. LN, BT, PM) by using
    :class:`openquake.baselib.general.CallableDict`
    """

    @abc.abstractmethod
    def sample(self, means, covs, stddevs, idxs):
        """
        :returns: sample a set of losses
        :param means: an array of mean losses
        :param covs: an array of covariances
        :param stddevs: an array of stddevs
        """
        raise NotImplementedError

    @abc.abstractmethod
    def survival(self, loss_ratio, mean, stddev):
        """
        Return the survival function of the distribution with `mean`
        and `stddev` applied to `loss_ratio`
        """
        raise NotImplementedError


class DegenerateDistribution(Distribution):
    """
    The degenerate distribution. E.g. a distribution with a delta
    corresponding to the mean.
    """
    def sample(self, means, _covs, _stddev, _idxs):
        return means

    def survival(self, loss_ratio, mean, _stddev):
        return numpy.piecewise(
            loss_ratio, [loss_ratio > mean or not mean], [0, 1])


def make_epsilons(matrix, seed, correlation):
    """
    Given a matrix N * R returns a matrix of the same shape N * R
    obtained by applying the multivariate_normal distribution to
    N points and R samples, by starting from the given seed and
    correlation.
    """
    if seed is not None:
        numpy.random.seed(seed)
    asset_count = len(matrix)
    samples = len(matrix[0])
    if not correlation:  # avoid building the covariance matrix
        return numpy.random.normal(size=(samples, asset_count)).transpose()
    means_vector = numpy.zeros(asset_count)
    covariance_matrix = (
        numpy.ones((asset_count, asset_count)) * correlation +
        numpy.diag(numpy.ones(asset_count)) * (1 - correlation))
    return numpy.random.multivariate_normal(
        means_vector, covariance_matrix, samples).transpose()


@DISTRIBUTIONS.add('LN')
class LogNormalDistribution(Distribution):
    """
    Model a distribution of a random variable whoose logarithm are
    normally distributed.

    :attr epsilons: An array of random numbers generated with
                    :func:`numpy.random.multivariate_normal` with size E
    """
    def __init__(self, epsilons=None):
        self.epsilons = epsilons

    def sample(self, means, covs, _stddevs, idxs):
        if self.epsilons is None:
            raise ValueError("A LogNormalDistribution must be initialized "
                             "before you can use it")
        eps = self.epsilons[idxs]
        sigma = numpy.sqrt(numpy.log(covs ** 2.0 + 1.0))
        probs = means / numpy.sqrt(1 + covs ** 2) * numpy.exp(eps * sigma)
        return probs

    def survival(self, loss_ratio, mean, stddev):
        # scipy does not handle correctly the limit case stddev = 0.
        # In that case, when `mean` > 0 the survival function
        # approaches to a step function, otherwise (`mean` == 0) we
        # returns 0
        if stddev == 0:
            return numpy.piecewise(
                loss_ratio, [loss_ratio > mean or not mean], [0, 1])

        variance = stddev ** 2.0

        sigma = numpy.sqrt(numpy.log((variance / mean ** 2.0) + 1.0))
        mu = mean ** 2.0 / numpy.sqrt(variance + mean ** 2.0)
        return stats.lognorm.sf(loss_ratio, sigma, scale=mu)


@DISTRIBUTIONS.add('BT')
class BetaDistribution(Distribution):
    def sample(self, means, _covs, stddevs, _idxs=None):
        alpha = self._alpha(means, stddevs)
        beta = self._beta(means, stddevs)
        return numpy.random.beta(alpha, beta, size=None)

    def survival(self, loss_ratio, mean, stddev):
        return stats.beta.sf(loss_ratio,
                             self._alpha(mean, stddev),
                             self._beta(mean, stddev))

    @staticmethod
    def _alpha(mean, stddev):
        return ((1 - mean) / stddev ** 2 - 1 / mean) * mean ** 2

    @staticmethod
    def _beta(mean, stddev):
        return ((1 - mean) / stddev ** 2 - 1 / mean) * (mean - mean ** 2)


@DISTRIBUTIONS.add('PM')
class DiscreteDistribution(Distribution):
    seed = None  # to be set

    def sample(self, loss_ratios, probs):
        ret = []
        r = numpy.arange(len(loss_ratios))
        for i in range(probs.shape[1]):
            random.seed(self.seed)
            # the seed is set inside the loop to avoid block-size dependency
            pmf = stats.rv_discrete(name='pmf', values=(r, probs[:, i])).rvs()
            ret.append(loss_ratios[pmf])
        return ret

    def survival(self, loss_ratios, probs):
        """
        Required for the Classical Risk and BCR Calculators.
        Currently left unimplemented as the PMF format is used only for the
        Scenario and Event Based Risk Calculators.

        :param int steps: number of steps between loss ratios.
        """
        # TODO: to be implemented if the classical risk calculator
        # needs to support the pmf vulnerability format
        return


#
# Event Based
#

class CurveBuilder(object):
    """
    Build loss ratio curves. The loss ratios can be provided
    by the user or automatically generated (user_provided=False).
    The usage is something like this:

      builder = CurveBuilder(loss_type, loss_ratios, ses_ratio,
                             user_provided=True)
      counts = builder.build_counts(loss_matrix)
    """
    def __init__(self, loss_type, curve_resolution, loss_ratios, ses_ratio,
                 user_provided, conditional_loss_poes=(),
                 insured_losses=False):
        self.loss_type = loss_type
        self.curve_resolution = curve_resolution
        self.ratios = numpy.array(loss_ratios, F32)
        self.ses_ratio = ses_ratio
        self.user_provided = user_provided
        self.conditional_loss_poes = conditional_loss_poes
        self.insured_losses = insured_losses

    def __call__(self, assets, ratios_by_aid):
        """"
        :param assets: a list of assets
        :param ratios_by_aid: a dictionary of loss ratios by asset ordinal
        :returns:
           two arrays, `aids` of size A, and `all_poes` of shape (A, I, C)
        """
        aids = []
        all_poes = []
        for asset in assets:
            aid = asset.ordinal
            try:
                loss_ratios = ratios_by_aid[aid]['loss']
            except KeyError:   # no loss ratios
                continue
            counts = numpy.array([(loss_ratios >= ratio).sum(axis=0)
                                  for ratio in self.ratios])
            poes = build_poes(counts, 1. / self.ses_ratio)
            if len(poes.shape) == 1:
                poes = poes[:, None]
            # for instance the ratios can have shape (21,), the loss_ratios
            # (3, 2), the counts (21, 2) and the transposed poes (2, 21)
            all_poes.append(poes.T)
            aids.append(aid)
        return numpy.array(aids), numpy.array(all_poes)

    def calc_agg_curve(self, losses):
        """
        :param losses: array of shape (E, I)
        :returns: curve of dtype agg_curve_dt
        """
        I = self.insured_losses + 1
        C = self.curve_resolution
        lp = numpy.zeros((2, C, I), F32)  # losses, poes
        avg = numpy.zeros(I, F32)
        if I == 1:
            losses = losses[:, None]  # extend 1-d
        lp[:, :, 0] = event_based(losses[:, 0], self.ses_ratio, C)
        avg[0] = average_loss(lp[:, :, 0])
        if I == 2:
            lp[:, :, 1] = event_based(losses[:, 1], self.ses_ratio, C)
            avg[1] = average_loss(lp[:, :, 1])
        agg_curve_dt = numpy.dtype([('losses', (F32, (I, C))),
                                    ('poes', (F32, (I, C))),
                                    ('avg', (F32, (I,)))])
        curve = numpy.zeros(1, agg_curve_dt)
        curve[0]['losses'] = lp[0].T
        curve[0]['poes'] = lp[1].T
        curve[0]['avg'] = avg
        return curve[0]

    def _calc_loss_maps(self, asset_values, clp, poe_matrix):
        """
        Compute loss maps from the PoE matrix (i.e. the loss curves).

        :param asset_values: asset values for the current loss type
        :param clp: conditional loss PoE
        :poe_matrix: an N x C matrix of PoEs
        :returns: a vector of N values
        """
        curves = []
        for avalue, poes in zip(asset_values, poe_matrix):
            curves.append((self.ratios * avalue, poes))
        return loss_map_matrix([clp], curves)[0]

    def build_loss_maps(self, assetcol, rcurves):
        """
        Build loss maps from the risk curves. Yield pairs
        (rlz_ordinal, loss_maps array).

        :param assetcol: asset collection
        :param rcurves: array of risk curves of shape (N, R, 2)
        """
        N = len(assetcol)
        R = rcurves.shape[1]
        if self.user_provided:  # loss_ratios provided
            lst = [('poe-%s' % poe, F32) for poe in self.conditional_loss_poes]
            if self.insured_losses:
                lst += [(name + '_ins', pair) for name, pair in lst]
            loss_maps_dt = numpy.dtype(lst)
            if self.loss_type == 'occupants':
                asset_values = assetcol['occupants']
            else:
                asset_values = assetcol['value-' + self.loss_type]
            curves_lt = rcurves[self.loss_type]
            for rlzi in range(R):
                loss_maps = numpy.zeros(N, loss_maps_dt)
                for name in loss_maps.dtype.names:
                    poe, ins = extract_poe_ins(name)
                    loss_maps[name] = self._calc_loss_maps(
                        asset_values, poe, curves_lt[:, rlzi, ins])
                yield rlzi, loss_maps

    def __repr__(self):
        return '<%s %s=%s user_provided=%s>' % (
            self.__class__.__name__, self.loss_type,
            self.ratios, self.user_provided)


# should I use the ses_ratio here?
def build_poes(counts, nses):
    """
    :param counts: an array of counts of exceedence for the bins
    :param nses: number of stochastic event sets
    :returns: an array of PoEs
    """
    return 1. - numpy.exp(- numpy.array(counts, F32) / nses)


def event_based(loss_values, ses_ratio, curve_resolution):
    """
    Compute a loss (or loss ratio) curve.

    :param loss_values: The loss ratios (or the losses) computed by
                        applying the vulnerability function

    :param ses_ratio: Time representative of the stochastic event set

    :param curve_resolution: The number of points the output curve is
                             defined by

    """
    reference_losses = numpy.linspace(
        0, numpy.max(loss_values), curve_resolution)
    # counts how many loss_values are bigger than the reference loss
    counts = [(loss_values > loss).sum() for loss in reference_losses]
    # NB: (loss_values > loss).sum() is MUCH more efficient than
    # sum(loss_values > loss). Incredibly more efficient in memory.
    return numpy.array(
        [reference_losses, build_poes(counts, 1. / ses_ratio)])


#
# Scenario Damage
#

def scenario_damage(fragility_functions, gmv):
    """
    Compute the damage state fractions for the given ground motion value.
    Return am array of M values where M is the numbers of damage states.
    """
    return pairwise_diff(
        [1] + [ff(gmv) for ff in fragility_functions] + [0])

#
# Classical Damage
#


def annual_frequency_of_exceedence(poe, t_haz):
    """
    :param poe: hazard probability of exceedence
    :param t_haz: hazard investigation time
    """
    return - numpy.log(1. - poe) / t_haz


def classical_damage(
        fragility_functions, hazard_imls, hazard_poes,
        investigation_time, risk_investigation_time):
    """
    :param fragility_functions:
        a list of fragility functions for each damage state
    :param hazard_imls:
        Intensity Measure Levels
    :param hazard_poes:
        hazard curve
    :param investigation_time:
        hazard investigation time
    :param risk_investigation_time:
        risk investigation time
    :returns:
        an array of M probabilities of occurrence where M is the numbers
        of damage states.
    """
    spi = fragility_functions.steps_per_interval
    if spi and spi > 1:  # interpolate
        imls = numpy.array(fragility_functions.interp_imls)
        min_val, max_val = hazard_imls[0], hazard_imls[-1]
        numpy.putmask(imls, imls < min_val, min_val)
        numpy.putmask(imls, imls > max_val, max_val)
        poes = interpolate.interp1d(hazard_imls, hazard_poes)(imls)
    else:
        imls = (hazard_imls if fragility_functions.format == 'continuous'
                else fragility_functions.imls)
        poes = numpy.array(hazard_poes)
    afe = annual_frequency_of_exceedence(poes, investigation_time)
    annual_frequency_of_occurrence = pairwise_diff(
        pairwise_mean([afe[0]] + list(afe) + [afe[-1]]))
    poes_per_damage_state = []
    for ff in fragility_functions:
        frequency_of_exceedence_per_damage_state = numpy.dot(
            annual_frequency_of_occurrence, list(map(ff, imls)))
        poe_per_damage_state = 1. - numpy.exp(
            - frequency_of_exceedence_per_damage_state *
            risk_investigation_time)
        poes_per_damage_state.append(poe_per_damage_state)
    poos = pairwise_diff([1] + poes_per_damage_state + [0])
    return poos

#
# Classical
#


def classical(vulnerability_function, hazard_imls, hazard_poes, steps=10):
    """
    :param vulnerability_function:
        an instance of
        :py:class:`openquake.risklib.scientific.VulnerabilityFunction`
        representing the vulnerability function used to compute the curve.
    :param hazard_imls:
        the hazard intensity measure type and levels
    :type hazard_poes:
        the hazard curve
    :param int steps:
        Number of steps between loss ratios.
    """
    assert len(hazard_imls) == len(hazard_poes), (
        len(hazard_imls), len(hazard_poes))
    vf = vulnerability_function
    imls = vf.mean_imls()
    loss_ratios, lrem = vf.loss_ratio_exceedance_matrix(steps)

    # saturate imls to hazard imls
    min_val, max_val = hazard_imls[0], hazard_imls[-1]
    numpy.putmask(imls, imls < min_val, min_val)
    numpy.putmask(imls, imls > max_val, max_val)

    # interpolate the hazard curve
    poes = interpolate.interp1d(hazard_imls, hazard_poes)(imls)

    # compute the poos
    pos = pairwise_diff(poes)
    lrem_po = numpy.empty(lrem.shape)
    for idx, po in enumerate(pos):
        lrem_po[:, idx] = lrem[:, idx] * po  # column * po
    return numpy.array([loss_ratios, lrem_po.sum(axis=1)])


def conditional_loss_ratio(loss_ratios, poes, probability):
    """
    Return the loss ratio corresponding to the given PoE (Probability
    of Exceendance). We can have four cases:

      1. If `probability` is in `poes` it takes the bigger
         corresponding loss_ratios.

      2. If it is in `(poe1, poe2)` where both `poe1` and `poe2` are
         in `poes`, then we perform a linear interpolation on the
         corresponding losses

      3. if the given probability is smaller than the
         lowest PoE defined, it returns the max loss ratio .

      4. if the given probability is greater than the highest PoE
         defined it returns zero.

    :param loss_ratios: an iterable over non-decreasing loss ratio
                        values (float)
    :param poes: an iterable over non-increasing probability of
                 exceedance values (float)
    :param float probability: the probability value used to
                              interpolate the loss curve
    """

    rpoes = poes[::-1]
    if probability > poes[0]:  # max poes
        return 0.0
    elif probability < poes[-1]:  # min PoE
        return loss_ratios[-1]
    if probability in poes:
        return max([loss
                    for i, loss in enumerate(loss_ratios)
                    if probability == poes[i]])
    else:
        interval_index = bisect.bisect_right(rpoes, probability)

        if interval_index == len(poes):  # poes are all nan
            return float('nan')
        elif interval_index == 1:  # boundary case
            x1, x2 = poes[-2:]
            y1, y2 = loss_ratios[-2:]
        else:
            x1, x2 = poes[-interval_index-1:-interval_index + 1]
            y1, y2 = loss_ratios[-interval_index-1:-interval_index + 1]

        return (y2 - y1) / (x2 - x1) * (probability - x1) + y1


#
# Insured Losses
#

def insured_losses(losses, deductible, insured_limit):
    """
    :param losses: an array of ground-up loss ratios
    :param float deductible: the deductible limit in fraction form
    :param float insured_limit: the insured limit in fraction form

    Compute insured losses for the given asset and losses, from the point
    of view of the insurance company. For instance:

    >>> insured_losses(numpy.array([3, 20, 101]), 5, 100)
    array([ 0, 15, 95])

    - if the loss is 3 (< 5) the company does not pay anything
    - if the loss is 20 the company pays 20 - 5 = 15
    - if the loss is 101 the company pays 100 - 5 = 95
    """
    return numpy.piecewise(
        losses,
        [losses < deductible, losses > insured_limit],
        [0, insured_limit - deductible, lambda x: x - deductible])


def insured_loss_curve(curve, deductible, insured_limit):
    """
    Compute an insured loss ratio curve given a loss ratio curve

    :param curve: an array 2 x R (where R is the curve resolution)
    :param float deductible: the deductible limit in fraction form
    :param float insured_limit: the insured limit in fraction form

    >>> losses = numpy.array([3, 20, 101])
    >>> poes = numpy.array([0.9, 0.5, 0.1])
    >>> insured_loss_curve(numpy.array([losses, poes]), 5, 100)
    array([[  3.        ,  20.        ],
           [  0.85294118,   0.5       ]])
    """
    losses, poes = curve[:, curve[0] <= insured_limit]
    limit_poe = interpolate.interp1d(
        *curve, bounds_error=False, fill_value=1)(deductible)
    return numpy.array([
        losses,
        numpy.piecewise(poes, [poes > limit_poe], [limit_poe, lambda x: x])])


#
# Benefit Cost Ratio Analysis
#


def bcr(eal_original, eal_retrofitted, interest_rate,
        asset_life_expectancy, asset_value, retrofitting_cost):
    """
    Compute the Benefit-Cost Ratio.

    BCR = (EALo - EALr)(1-exp(-r*t))/(r*C)

    Where:

    * BCR -- Benefit cost ratio
    * EALo -- Expected annual loss for original asset
    * EALr -- Expected annual loss for retrofitted asset
    * r -- Interest rate
    * t -- Life expectancy of the asset
    * C -- Retrofitting cost
    """
    return ((eal_original - eal_retrofitted) * asset_value *
            (1 - numpy.exp(- interest_rate * asset_life_expectancy)) /
            (interest_rate * retrofitting_cost))


# ####################### statistics #################################### #

def pairwise_mean(values):
    "Averages between a value and the next value in a sequence"
    return numpy.array([numpy.mean(pair) for pair in utils.pairwise(values)])


def pairwise_diff(values):
    "Differences between a value and the next value in a sequence"
    return numpy.array([x - y for x, y in utils.pairwise(values)])


def mean_std(fractions):
    """
    Given an N x M matrix, returns mean and std computed on the rows,
    i.e. two M-dimensional vectors.
    """
    return numpy.mean(fractions, axis=0), numpy.std(fractions, axis=0, ddof=1)


def loss_map_matrix(poes, curves):
    """
    Wrapper around :func:`openquake.risklib.scientific.conditional_loss_ratio`.
    Return a matrix of shape (num-poes, num-curves). The curves are lists of
    pairs (loss_ratios, poes).
    """
    return numpy.array(
        [[conditional_loss_ratio(curve[0], curve[1], poe)
          for curve in curves] for poe in poes]
    ).reshape((len(poes), len(curves)))


# TODO: remove this from openquake.risklib.qa_tests.bcr_test
def average_loss(losses_poes):
    """
    Given a loss curve with `poes` over `losses` defined on a given
    time span it computes the average loss on this period of time.

    :note: As the loss curve is supposed to be piecewise linear as it
           is a result of a linear interpolation, we compute an exact
           integral by using the trapeizodal rule with the width given by the
           loss bin width.
    """
    losses, poes = losses_poes
    return numpy.dot(-pairwise_diff(losses), pairwise_mean(poes))


def quantile_matrix(values, quantiles, weights):
    """
    :param curves:
        a matrix R x N, where N is the number of assets and R the number
        of realizations
    :param quantile:
        a list of Q quantiles
    :param weights:
        a list of R weights
    :returns:
        a matrix Q x N
    """
    result = numpy.zeros((len(quantiles), values.shape[1]))
    for i, q in enumerate(quantiles):
        result[i] = quantile_curve(values, q, weights)
    return result


def exposure_statistics(
        multicurves, map_poes, weights, quantiles):
    """
    Compute exposure statistics for N assets and R realizations.

    :param multicurves:
        a list with N loss curves data. Each item holds a 2-tuple with
        1) the loss ratios on which the curves have been defined on
        2) the poes of the R curves
    :param map_poes:
        a numpy array with P poes used to compute loss maps
    :param weights:
        a list of N weights used to compute mean/quantile weighted statistics
    :param quantiles:
        the quantile levels used to compute quantile results

    :returns:
        a tuple with four elements:
            1. a numpy array with N mean loss curves
            2. a numpy array with P x N mean map values
            3. a numpy array with Q x N quantile loss curves
            4. a numpy array with Q x P quantile map values
    """
    curve_resolution = len(multicurves[0].losses)
    map_nr = len(map_poes)

    # Collect per-asset statistic along the last dimension of the
    # following arrays
    mean_curves = numpy.zeros((0, 2, curve_resolution))
    mean_maps = numpy.zeros((map_nr, 0))
    quantile_curves = numpy.zeros((len(quantiles), 0, 2, curve_resolution))
    quantile_maps = numpy.zeros((len(quantiles), map_nr, 0))

    for mcurve in multicurves:
        _mean_curve, _mean_maps, _quantile_curves, _quantile_maps = (
            mcurve.statistics(quantiles, weights, map_poes))

        mean_curves = numpy.vstack(
            (mean_curves, _mean_curve[numpy.newaxis, :]))
        mean_maps = numpy.hstack((mean_maps, _mean_maps[:, numpy.newaxis]))

        quantile_curves = numpy.hstack(
            (quantile_curves, _quantile_curves[:, numpy.newaxis]))
        quantile_maps = numpy.dstack(
            (quantile_maps, _quantile_maps[:, :, numpy.newaxis]))

    return (mean_curves, mean_maps, quantile_curves, quantile_maps)


def normalize_curves(curves):
    """
    :param curves: a list of pairs (losses, poes)
    :returns: first losses, all_poes
    """
    return curves[0][0], [poes for _losses, poes in curves]


def normalize_curves_eb(curves):
    """
    A more sophisticated version of normalize_curves, used in the event
    based calculator.

    :param curves: a list of pairs (losses, poes)
    :returns: first losses, all_poes
    """
    # we assume non-decreasing losses, so losses[-1] is the maximum loss
    non_zero_curves = [(losses, poes)
                       for losses, poes in curves if losses[-1] > 0]
    if not non_zero_curves:  # no damage. all zero curves
        return curves[0][0], [poes for _losses, poes in curves]
    else:  # standard case
        max_losses = [losses[-1] for losses, _poes in non_zero_curves]
        reference_curve = non_zero_curves[numpy.argmax(max_losses)]
        loss_ratios = reference_curve[0]
        curves_poes = [interpolate.interp1d(
            losses, poes, bounds_error=False, fill_value=0)(loss_ratios)
            for losses, poes in curves]
        # fix degenerated case with flat curve
        for cp in curves_poes:
            if numpy.isnan(cp[0]):
                cp[0] = 0
    return loss_ratios, curves_poes


class SimpleStats(object):
    """
    A class to perform statistics on the average losses. The average losses
    are stored as N x 2 arrays (non-insured and insured losses) where N is
    the number of assets.

    :param rlzs: a list of realizations
    :param quantiles: a list of floats in the range 0..1
    """
    def __init__(self, rlzs, quantiles=()):
        self.rlzs = rlzs
        self.quantiles = quantiles
        self.names = ['mean'] + ['quantile-%s' % q for q in quantiles]

    def compute(self, name, dstore):
        """
        Compute mean and quantiles from the data in the datastore
        under the group `<name>-rlzs`. Returns an array of shape (N, Q1).
        """
        weights = [rlz.weight for rlz in self.rlzs]
        rlzsname = name + '-rlzs'
        array = dstore[rlzsname].value
        newshape = list(array.shape)
        newshape[1] = len(self.quantiles) + 1  # number of statistical outputs
        newarray = numpy.zeros(newshape, array.dtype)
        data = [array[:, i] for i in range(len(self.rlzs))]
        newarray[:, 0] = mean_curve(data, weights)
        for i, q in enumerate(self.quantiles, 1):
            newarray[:, i] = quantile_curve(data, q, weights)
        return newarray


def build_loss_dtypes(curve_resolution, conditional_loss_poes, insured_losses):
    """
    :param curve_resolution:
        dictionary loss_type -> curve_resolution
    :param conditional_loss_poes:
        configuration parameter
    :param insured_losses:
        configuration parameter
    :returns:
       loss_curve_dt and loss_maps_dt
    """
    lst = [('poe-%s' % poe, F32) for poe in conditional_loss_poes]
    if insured_losses:
        lst += [(name + '_ins', pair) for name, pair in lst]
    lm_dt = numpy.dtype(lst)
    lc_list = []
    lm_list = []
    for lt in sorted(curve_resolution):
        C = curve_resolution[lt]
        pairs = [('losses', (F32, C)), ('poes', (F32, C)), ('avg', F32)]
        if insured_losses:
            pairs += [(name + '_ins', pair) for name, pair in pairs]
        lc_list.append((str(lt), numpy.dtype(pairs)))
        lm_list.append((str(lt), lm_dt))
    loss_curve_dt = numpy.dtype(lc_list) if lc_list else None
    loss_maps_dt = numpy.dtype(lm_list) if lm_list else None
    return loss_curve_dt, loss_maps_dt


class StatsBuilder(object):
    """
    A class to build risk statistics.

    :param quantiles: list of quantile values
    :param conditional_loss_poes: list of conditional loss poes
    :param curve_resolution: only meaninful for the event based
    """
    def __init__(self, quantiles,
                 conditional_loss_poes,
                 _normalize_curves=normalize_curves,
                 insured_losses=False):
        self.quantiles = quantiles
        self.conditional_loss_poes = conditional_loss_poes
        self.normalize_curves = _normalize_curves
        self.insured_losses = insured_losses
        self.mean_quantiles = ['mean']
        for q in quantiles:
            self.mean_quantiles.append('quantile-%s' % q)

    def normalize(self, loss_curves):
        """
        Normalize the loss curves by using the provided normalization function
        """
        return [MultiCurve(*self.normalize_curves(curves))
                for curves in numpy.array(loss_curves).transpose(1, 0, 2, 3)]

    def build(self, all_outputs, prefix=''):
        """
        Build all statistics from a set of risk outputs.

        :param all_outputs:
            a non empty sequence of risk outputs referring to the same assets
            and loss_type. Each output must have attributes assets, loss_type,
            hid, weight, loss_curves and insured_curves (the latter is
            possibly None).
        :returns:
            an Output object with the following attributes
            (numpy arrays; the shape is in parenthesis, N is the number of
            assets, R the resolution of the loss curve, P the number of
            conditional loss poes, Q the number of quantiles):

            01. assets (N)
            02. loss_type (1)
            03. mean_curves (2, N, 2, R)
            04. mean_average_losses (2, N)
            05. mean_map (2, P, N)
            06. mean_fractions (2, P, N)
            07. quantile_curves (2, Q, N, 2, R)
            08. quantile_average_losses (2, Q, N)
            09. quantile_maps (2, Q, P, N)
            10. quantile_fractions (2, Q, P, N)
            11. quantiles (Q)
        """
        outputs = []
        weights = []
        loss_curves = []
        average_losses = []
        average_ins_losses = []
        for out in all_outputs:
            outputs.append(out)
            weights.append(out.weight)
            loss_curves.append(out.loss_curves)
            average_losses.append(out.average_losses)
            average_ins_losses.append(out.average_insured_losses)
        average_losses = numpy.array(average_losses, F32)
        mean_average_losses = mean_curve(average_losses, weights)
        quantile_average_losses = quantile_matrix(
            average_losses, self.quantiles, weights)
        mean_curves, mean_maps, q_curves, q_maps = exposure_statistics(
            self.normalize(loss_curves),
            self.conditional_loss_poes, weights, self.quantiles)
        if outputs[0].insured_curves is not None:
            average_ins_losses = numpy.array(average_ins_losses, F32)
            mean_average_ins_losses = mean_curve(average_ins_losses, weights)
            quantile_average_ins_losses = quantile_matrix(
                average_ins_losses, self.quantiles, weights)
            loss_curves = [out.insured_curves for out in outputs]
            mean_ins_curves, mean_ins_maps, q_ins_curves, q_ins_maps = (
                exposure_statistics(
                    self.normalize(loss_curves), [], weights, self.quantiles))
        else:
            mean_ins_curves = numpy.zeros_like(mean_curves)
            mean_average_ins_losses = numpy.zeros_like(mean_average_losses)
            mean_ins_maps = numpy.zeros_like(mean_maps)
            q_ins_maps = numpy.zeros_like(q_maps)
            q_ins_curves = numpy.zeros_like(q_curves)
            quantile_average_ins_losses = numpy.zeros_like(
                quantile_average_losses)

        P = len(self.conditional_loss_poes)
        loss_type = outputs[0].loss_type
        return Output(
            assets=outputs[0].assets,
            loss_type=loss_type,
            mean_curves=[mean_curves, mean_ins_curves],
            mean_average_losses=[mean_average_losses, mean_average_ins_losses],
            mean_maps=[mean_maps[0:P, :], mean_ins_maps[0:P, :]],
            # P x N matrix
            mean_fractions=[mean_maps[P:, :], mean_ins_maps[P:, :]],
            # P x N matrix
            quantile_curves=[q_curves, q_ins_curves],
            # (Q, N, 2, R) matrix
            quantile_average_losses=[quantile_average_losses,
                                     quantile_average_ins_losses],
            quantile_maps=[q_maps[:, 0:P], q_ins_maps[:, 0:P]],
            # Q x P x N matrix
            quantile_fractions=[q_maps[:, P:], q_ins_maps[:, P:]],
            # Q x P x N matrix
            quantiles=self.quantiles,
            conditional_loss_poes=self.conditional_loss_poes,
            prefix=prefix)

    def get_curves_maps(self, outputs_by_lt, loss_ratios_by_lt):
        """
        :param outputs_by_lt:
            for each loss type, a list with R outputs
        :param loss_ratios_by_lt:
            for each loss_type, an array of ratios
        """
        loss_curve_dt, loss_maps_dt = build_loss_dtypes(
            {lt: len(loss_ratios_by_lt[lt]) for lt in loss_ratios_by_lt},
            self.conditional_loss_poes, self.insured_losses)
        assets = list(outputs_by_lt.values())[0][0].assets
        N = len(assets)
        Q1 = len(self.mean_quantiles)
        loss_curves = numpy.zeros((N, Q1), loss_curve_dt)
        if self.conditional_loss_poes:
            loss_maps = numpy.zeros((N, Q1), loss_maps_dt)
        else:
            loss_maps = None
        for lt in loss_ratios_by_lt:
            C = loss_curve_dt[lt]['losses'].shape[-1]
            curves, maps = self._get_curves_maps(
                self.build(outputs_by_lt[lt]), C)
            loss_curves[lt] = curves.T
            if self.conditional_loss_poes:
                loss_maps[lt] = maps.T
        return loss_curves, loss_maps

    def _get_curves_maps(self, stats, C):
        """
        :param stats:
            an object with attributes mean_curves, mean_average_losses,
            mean_maps, quantile_curves, quantile_average_losses,
            quantile_loss_curves, quantile_maps, assets.
            There is also a loss_type attribute which must be always the same.
        :param C:
             curve resolution
        :returns:
            statistical loss curves and maps per asset as composite arrays
            of shape (Q1, N)
        """
        loss_curve_dt, loss_maps_dt = build_dtypes(
            C, self.conditional_loss_poes, self.insured_losses)

        Q1 = len(self.mean_quantiles)
        N = len(stats.assets)
        curves = numpy.zeros((Q1, N), loss_curve_dt)
        if self.conditional_loss_poes:
            maps = numpy.zeros((Q1, N), loss_maps_dt)
            poenames = [n for n in loss_maps_dt.names
                        if not n.endswith('_ins')]
        else:
            maps = []
        for i in range(self.insured_losses + 1):  # insured index
            ins = '_ins' if i else ''
            curves_by_stat = self._loss_curves(
                stats.mean_curves[i],
                stats.mean_average_losses[i],
                stats.quantile_curves[i],
                stats.quantile_average_losses[i])
            for aid, pairs in enumerate(curves_by_stat):
                for s, (losses_poes, avg) in enumerate(pairs):
                    curves['losses' + ins][s, aid] = losses_poes[0]
                    curves['poes' + ins][s, aid] = losses_poes[1]
                    curves['avg' + ins][s, aid] = avg

            if self.conditional_loss_poes:
                mq = _combine_mq(stats.mean_maps[i], stats.quantile_maps[i])
                for aid, maps_ in enumerate(mq):
                    for name, map_ in zip(poenames, maps_):
                        maps[name + ins][aid] = map_
        return curves, maps

    def _loss_curves(self, mean, mean_averages, quantile, quantile_averages):
        mq_curves = _combine_mq(mean, quantile)  # shape (Q1, N, 2, C)
        mq_avgs = _combine_mq(mean_averages, quantile_averages)  # (Q1, N)
        acc = []
        for mq_curve, mq_avg in zip(
                mq_curves.transpose(1, 0, 2, 3), mq_avgs.T):
            acc.append(zip(mq_curve, mq_avg))
        return acc  # (N, Q1) triples

    def build_agg_curve_stats(self, loss_curve_dt, dstore):
        """
        Build an array `agg_curve-stats`.

        :param loss_curve_dt:
            numpy dtype with fields (structural~losses, structural~poes,
            structural~avg, ...)
        :param dstore:
            :class:`openquake.commonlib.datastore.DataStore` instance
        :returns:
            an array of size Q1 and dtype loss_curve_dt
        """
        rlzs = dstore['csm_info'].get_rlzs_assoc().realizations
        Q1 = len(self.mean_quantiles)
        agg_curve_stats = numpy.zeros(Q1, loss_curve_dt)
        for l, loss_type in enumerate(loss_curve_dt.names):
            agg_curve_lt = dstore['agg_curve-rlzs'][loss_type]
            C = agg_curve_lt['losses'].shape[-1]
            outputs = []
            for rlz in rlzs:
                curve = agg_curve_lt[rlz.ordinal]
                average_loss = curve['avg'][0]
                loss_curve = (curve['losses'][0], curve['poes'][0])
                if self.insured_losses:
                    average_insured_loss = curve['avg'][1]
                    insured_curves = [(curve['losses'][1], curve['poes'][1])]
                else:
                    average_insured_loss = None
                    insured_curves = None
                out = Output(
                    [None], loss_type, rlz.ordinal, rlz.weight,
                    loss_curves=[loss_curve],
                    insured_curves=insured_curves,
                    average_losses=[average_loss],
                    average_insured_losses=[average_insured_loss])
                outputs.append(out)
            stats = self.build(outputs)
            curves, _maps = self._get_curves_maps(stats, C)  # shape (Q1, 1)
            acs = agg_curve_stats[loss_type]
            for i, statname in enumerate(self.mean_quantiles):
                for name in acs.dtype.names:
                    acs[name][i] = curves[name][i]
        return agg_curve_stats


def _old_loss_curves(asset_values, rcurves, ratios):
    # build loss curves in the old format (i.e. (losses, poes)) from
    # loss curves in the new format (i.e. poes).
    # shape (N, 2, C)
    return numpy.array([(avalue * ratios, poes)
                        for avalue, poes in zip(asset_values, rcurves)])


def _combine_mq(mean, quantile):
    # combine mean and quantile into a single array of length Q + 1
    shape = mean.shape
    Q = len(quantile)
    assert quantile.shape[1:] == shape, (quantile.shape[1:], shape)
    array = numpy.zeros((Q + 1,) + shape)
    array[0] = mean
    array[1:] = quantile
    return array


class MultiCurve(object):
    """
    :param losses: an array of C losses
    :param all_poes: a list of R arrays of C PoEs
    """
    def __init__(self, losses, all_poes):
        self.losses = losses
        self.all_poes = all_poes

    def statistics(self, quantiles, weights, poes):
        """
        Compute output statistics (mean/quantile loss curves and maps)
        for a single asset
        :param list quantiles:
           quantile levels to be considered for quantile outputs
        : param list weights:
           realization weights
        :param list poes:
           the poe taken into account for computing loss maps
        :returns:
           a tuple with
           1) mean loss curve
           2) mean loss map
           3) a list of quantile curves
           4) a list of quantile loss maps
        """
        mean_curve_ = numpy.array(
            [self.losses, mean_curve(self.all_poes, weights)])
        mean_map = loss_map_matrix(poes, [mean_curve_]).reshape(len(poes))
        quantile_curves = numpy.array(
            [[self.losses, quantile_curve(self.all_poes, quantile, weights)]
             for quantile in quantiles]).reshape(
                     (len(quantiles), 2, len(self.losses)))
        quantile_maps = loss_map_matrix(poes, quantile_curves).transpose()
        return mean_curve_, mean_map, quantile_curves, quantile_maps
