# -*- coding: utf-8 -*-
# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright (C) 2013-2019 GEM Foundation
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
Module exports :class:`ITA04Base`
"""
import os
import numpy
from openquake.hazardlib.gsim.gmpe_table import GMPETable

BASE_PATH = os.path.dirname(__file__)


class ITA04Base(GMPETable):
    """
    This class is an general class used to implement the GMPEs used for the
    2004 version of the national hazard model for Italy.
    """

    def __init__(self, gmpe_table):
        """
        """
        super().__init__(gmpe_table=gmpe_table)
        self.init()

    """
    def get_mean_and_stddevs(self, sctx, rctx, dctx, imt, stddev_types):
        # Return imls
        imls = self._return_tables(rctx.mag, imt, "IMLs")
        # Get distance vector for the given magnitude
        idx = numpy.searchsorted(self.m_w, rctx.mag)
        dists = self.distances[:, 0, idx - 1]
        # Get mean and standard deviations
        mean = self._get_mean(imls, dctx, dists)
        stddevs = self._get_stddevs(stddev_types, len(dctx.repi))
        return numpy.log(mean), stddevs
    """


class AmbraseysEtAl1996Normal(ITA04Base):
    """
    This class implements an adjusted version of the Ambraseys et al. (1996)
    ground motion model as described in Stucchi et al. (2004).
    Document available at:
    http://zonesismiche.mi.ingv.it/elaborazioni/download.php)
    """
    path = "./ita04_tables/asb96_normal.hdf5"
    TABLE_PATH = os.path.abspath(os.path.join(BASE_PATH, path))

    def __init__(self):
        if not self.TABLE_PATH:
            raise NotImplementedError("hdf file not defined")
        super().__init__(gmpe_table=self.TABLE_PATH)


class AmbraseysEtAl1996Reverse(ITA04Base):
    """
    See :class:`openquake.hazardlib.gsim.ita04.AmbraseysEtAl1996Normal`
    """
    TABLE_PATH = os.path.abspath("./ita04_tables/asb96_reverse.hdf5")

    def __init__(self):
        if not self.TABLE_PATH:
            raise NotImplementedError("hdf file not defined")
        super().__init__(gmpe_table=self.TABLE_PATH)


class AmbraseysEtAl1996Strike(ITA04Base):
    """
    See :class:`openquake.hazardlib.gsim.ita04.AmbraseysEtAl1996Normal`
    """
    TABLE_PATH = os.path.abspath("./ita04_tables/asb96_strike.hdf5")

    def __init__(self):
        if not self.TABLE_PATH:
            raise NotImplementedError("hdf file not defined")
        super().__init__(gmpe_table=self.TABLE_PATH)


class AmbraseysEtAl1996Undef(ITA04Base):
    """
    See :class:`openquake.hazardlib.gsim.ita04.AmbraseysEtAl1996Normal`
    """
    TABLE_PATH = os.path.abspath("./ita04_tables/asb96_undef.hdf5")

    def __init__(self):
        if not self.TABLE_PATH:
            raise NotImplementedError("hdf file not defined")
        super().__init__(gmpe_table=self.TABLE_PATH)


class SabettaPugliese1996Normal(ITA04Base):
    """
    This class implements an adjusted version of the Sabetta e Pugliese (1996)
    ground motion model as described in Stucchi et al. (2004).
    Document available at:
    http://zonesismiche.mi.ingv.it/elaborazioni/download.php)

    """
    TABLE_PATH = os.path.abspath("./ita04_tables/sp96_normal.hdf5")

    def __init__(self):
        if not self.TABLE_PATH:
            raise NotImplementedError("This ")
        super().__init__(gmpe_table=self.TABLE_PATH)


class SabettaPugliese1996Reverse(ITA04Base):
    """
    See :class:`openquake.hazardlib.gsim.ita04.SabettaPugliese1996Normal`
    """
    TABLE_PATH = os.path.abspath("./ita04_tables/sp96_reverse.hdf5")

    def __init__(self):
        if not self.TABLE_PATH:
            raise NotImplementedError("This ")
        super().__init__(gmpe_table=self.TABLE_PATH)


class SabettaPugliese1996Strike(ITA04Base):
    """
    See :class:`openquake.hazardlib.gsim.ita04.SabettaPugliese1996Normal`
    """
    TABLE_PATH = os.path.abspath("./ita04_tables/sp96_strike.hdf5")

    def __init__(self):
        if not self.TABLE_PATH:
            raise NotImplementedError("This ")
        super().__init__(gmpe_table=self.TABLE_PATH)


class SabettaPugliese1996Undef(ITA04Base):
    """
    See :class:`openquake.hazardlib.gsim.ita04.SabettaPugliese1996Normal`
    """
    TABLE_PATH = os.path.abspath("./ita04_tables/sp96_undef.hdf5")

    def __init__(self):
        if not self.TABLE_PATH:
            raise NotImplementedError("This ")
        super().__init__(gmpe_table=self.TABLE_PATH)


class REG1(ITA04Base):
    """
    This class implements a set of regionalised GMM used in the calculation of
    hazard for the 2004 version of the Italy National Hazard model as described
    in Stucchi et al. (2004).
    Document available at:
    http://zonesismiche.mi.ingv.it/elaborazioni/download.php)
    """
    TABLE_PATH = os.path.abspath("./ita04_tables/reg1.hdf5")

    def __init__(self):
        if not self.TABLE_PATH:
            raise NotImplementedError("This ")
        super().__init__(gmpe_table=self.TABLE_PATH)


class REG2(ITA04Base):
    """
    See :class:`openquake.hazardlib.gsim.ita04.REG1`
    """
    TABLE_PATH = os.path.abspath("./ita04_tables/reg2.hdf5")

    def __init__(self):
        if not self.TABLE_PATH:
            raise NotImplementedError("This ")
        super().__init__(gmpe_table=self.TABLE_PATH)


class REG3(ITA04Base):
    """
    See :class:`openquake.hazardlib.gsim.ita04.REG1`
    """
    TABLE_PATH = os.path.abspath("./ita04_tables/reg3.hdf5")

    def __init__(self):
        if not self.TABLE_PATH:
            raise NotImplementedError("This ")
        super().__init__(gmpe_table=self.TABLE_PATH)


class VULC30bar(ITA04Base):
    TABLE_PATH = os.path.abspath("./ita04_tables/vulc30bar.hdf5")

    def __init__(self):
        if not self.TABLE_PATH:
            raise NotImplementedError("This ")
        super().__init__(gmpe_table=self.TABLE_PATH)


class VULC50bar(ITA04Base):
    TABLE_PATH = os.path.abspath("./ita04_tables/vulc50bar.hdf5")

    def __init__(self):
        if not self.TABLE_PATH:
            raise NotImplementedError("This ")
        super().__init__(gmpe_table=self.TABLE_PATH)