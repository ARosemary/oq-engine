"""
Module :mod:`nhe.msr.peer` implements :class:`PeerMSR`.
"""
from nhe.msr.base import BaseMSR


class PeerMSR(BaseMSR):
    """
    Magnitude-Scaling Relationship defined for PEER PSHA test cases.

    See "Verification of Probabilistic Seismic Hazard Analysis Computer
    Programs", Patricia Thomas and Ivan Wong, PEER Report 2010/106, May 2010.
    """
    def get_median_area(self, mag, rake, epsilon=0.0):
        """
        Calculates median area as ``10 ** (mag - 4)``. Rake is ignored.
        """
        return 10 ** (mag - 4.0 + 0.25 * epsilon)
