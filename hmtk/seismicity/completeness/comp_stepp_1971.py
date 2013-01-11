#/usr/bin/env/python

"""
Module :mod: 'hmtk.seismicity.completeness.comp_stepp_1972' defines the 
hmtk implementation of the Stepp (1972) algorithm for analysing the
completeness of an earthquake catalogue
"""

from math import fabs
import numpy as np
from scipy.optimize import fmin_l_bfgs_b
from hmtk.seismicity.utils import decimal_time, piecewise_linear_scalar
from hmtk.seismicity.completeness.base import BaseCatalogueCompleteness

def get_bilinear_residuals_stepp(input_params, xvals, yvals, slope1_fit):
    '''
    Returns the residual sum-of-squares value of a bilinear fit to a data
    set - with a segment - 1 gradient fixed by an input value (slope_1_fit)
    :param list input_params:
        Input parameters for the bilinear model [slope2, crossover_point,
                                                 intercept]
    :param numpy.ndarray xvals:
        x-values of the data to be fit
    
    :param numpy.ndarray yvals:
        y-values of the data to be fit
    
    :param float slope1_fit:
        Gradient of the first slope
    
    :returns:
        Residual sum-of-squares of fit
    '''
    params = np.hstack([slope1_fit, input_params])
    num_x = len(xvals)
    y_model = np.zeros(num_x, dtype=float)
    residuals = np.zeros(num_x, dtype=float)
    for iloc in range(0, num_x):
        y_model[iloc] = piecewise_linear_scalar(params, xvals[iloc])
        residuals[iloc] = (yvals[iloc] - y_model[iloc]) ** 2.0
    return np.sum(residuals)


class Stepp1971(BaseCatalogueCompleteness):
    '''
    Implements the completeness analysis methodology of Stepp (1972)
    Stepp, J. C. (1972) Analysis of Completeness of the Earhquake Sample in
    the Puget Sound Area and Its Effect on Statistical Estimates of Earthquake
    Hazard. NOAA Environmental Research Laboratories
    
    The original methodology of J. C. Stepp (1972) implements a graphical 
    method in which the devation of the observed rate from the expected
    Poisson rate is assessed by judgement. To implement the selection 
    in an automated fashion this implementation uses optimisation of a 
    2-segment piecewise linear fit to each magnitude bin, using the 
    segment intersection point to identify the completeness period.

    Adaptation implemented by Weatherill, G. A., GEM Model Facility, Pavia
    
    :attribute numpy.ndarray magnitude_bin:
        Edges of the magnitude bins

    :attribute numpy.ndarray sigma:
        Sigma lambda defined by Equation 4 in Stepp (1972)
    
    :attribute numpy.ndarray time_values:
        Duration values

    :attribute numpy.ndarray model_line:
        Expected Poisson rate for each magnitude bin

    :attribute numpy.ndarray completeness_table:
        Resulting completeness table
    '''
    
    def completeness(self, catalogue, config): 
        '''Gets the completeness table
        
        :param catalogue:
            Earthquake catalogue as instance of 
            :class: hmtk.seismicity.catalogue.Catalogue
        
        :param dict config:
            Configuration parameters of the algorithm, containing the 
            following information - 
                'magnitude_bin' Size of magnitude bin (non-negative float)
                'time_bin' Size (in dec. years) of the time window 
                           (non-negative float)
                'increment_lock' Boolean to indicate whether to ensure
                           completeness magnitudes always decrease with more
                           recent bins
        
        :returns: 
            2-column table indicating year of completeness and corresponding 
            magnitude numpy.ndarray
        '''
        # If mag_bin is an array then bins are input, otherwise a single 
        # parameter is input
        dyear = decimal_time(catalogue.data['year'],
		                     catalogue.data['month'],
							 catalogue.data['day'],
							 catalogue.data['hour'],
							 catalogue.data['minute'],
							 catalogue.data['second'])
        mag = catalogue.data['magnitude']

        # Get magnitude bins
        self.magnitude_bin = self._get_magnitudes_from_spacing(
            catalogue.data['magnitude'],
		    config['magnitude_bin'])

        # Get time bins
        start_year, time_bin = self._get_time_limits_from_config(config, dyear)
         
        # Count magnitudes
        self.sigma, counter, n_mags, n_times, self.time_values = \
            self._count_magnitudes(mag, dyear, time_bin)

        t_ref = 1.0 / np.sqrt(self.time_values)
        
        # Get completeness magnitudes
        comp_time, gradient_2, self.model_line = \
            self.get_completeness_points(self.time_values, self.sigma, n_mags,
                                         n_times)

        mag_cents = (self.magnitude_bin[1:] + self.magnitude_bin[:-1]) / 2.
        
        # If the increment lock is selected then ensure completeness time
        # does not decrease
        if config['increment_lock']:
            for iloc in range(0, len(comp_time)):
                if (iloc > 0 and (comp_time[iloc] < comp_time[iloc - 1])) or\
                    np.isnan(comp_time[iloc]):
                    comp_time[iloc] = comp_time[iloc - 1]

        self.completeness_table = np.column_stack([
            np.floor(self.end_year - comp_time), 
            mag_cents])
        
        return self.completeness_table 
    
   
    def _get_time_limits_from_config(self, config, dec_year):
        '''
        Defines the time bins for consideration based on the config time_bin
        settings - also sets self.end_year (int) the latest year in catalogue
        
        :param dict config:
            Configuration for the Stepp (1971) algorithm
        
        :param numpy.ndarray dec_year:
            Time of the earthquake in decimal years
        
        :returns:
            * start_year: Earliest year found in the catalogue
            * time_bin: Bin edges of the time windows
        ''' 
        if isinstance(config['time_bin'], list) or \
            isinstance(config['time_bin'], np.ndarray):
            # Check to make sure input years are in order from recent to oldest
            for ival in range(1, len(config['time_bin'])):
                if (config['time_bin'][ival] - 
                    config['time_bin'][ival - 1]) > 0.:
                    raise ValueError('Configuration time windows must be '
                        'ordered from recent to oldest!')

            self.end_year = config['time_bin'][0]
            start_year = config['time_bin'][-1]
            time_bin = np.array(config['time_bin'])
        else:
            self.end_year = np.floor(np.max(dec_year))
            start_year = np.floor(np.min(dec_year))
            if (self.end_year - start_year) < config['time_bin']:
                raise ValueError('Catalogue duration smaller than time bin'
                    ' width - change time window size!')
            time_bin = np.arange(self.end_year - config['time_bin'], 
                                 start_year - config['time_bin'], 
                                 -config['time_bin'])

        return start_year, time_bin

    def _get_magnitudes_from_spacing(self, magnitudes, delta_m):
        '''If a single magnitude spacing is input then create the bins
        
        :param numpy.ndarray magnitudes:
            Vector of earthquake magnitudes
        
        :param float delta_m:
            Magnitude bin width
        
        :returns: Vector of magnitude bin edges (numpy.ndarray)
        '''
        min_mag = np.min(magnitudes)
        max_mag = np.max(magnitudes)
        if (max_mag - min_mag) < delta_m:
            raise ValueError('Bin width greater than magnitude range!')
          
        mag_bins = np.arange(np.floor(min_mag), np.ceil(max_mag), delta_m)

        # Check to see if there are magnitudes in lower and upper bins
        is_mag = np.logical_and(mag_bins - max_mag < delta_m, 
                                min_mag - mag_bins < delta_m)
        mag_bins = mag_bins[is_mag]
        return mag_bins
	

    def _count_magnitudes(self, mags, times, time_bin):
        '''For each completeness magnitude-year counts the number of events
        inside each magnitude bin. 
        
        :param numpy.ndarray mags: 
            Magnitude of earthquakes
        
        :param numpy.ndarray times:
            Vector of decimal event times
        
        :param numpy.ndarray time_bin:
            Vector of bin edges of the time windows
        
        :returns:
            * sigma - Poisson variance (numpy.ndarray)
            * counter - Number of earthquakes in each magnitude-time bin
            * n_mags - number of magnitude bins (Integer)
            * n_times - number of time bins (Integer)
            * n_years - effective duration of each time window (numpy.ndarray)
        '''
        n_mags = len(self.magnitude_bin) - 1
        n_times = len(time_bin)
        counter = np.zeros([n_times, n_mags], dtype=int)
        # Count all the magnitudes later than or equal to the reference time 
        for iloc in range(0, n_times):
            id0 = times > time_bin[iloc]
            counter[iloc, :] = np.histogram(mags[id0], self.magnitude_bin)[0]
        # Get sigma_lambda  = sqrt(n / nyears) / sqrt(n_years) 
        sigma = np.zeros([n_times, n_mags], dtype=float)
        n_years = np.floor(np.max(times)) - time_bin
        for iloc in range(0, n_mags):
            id0 = counter[:, iloc] > 0
            if any(id0):
                nvals = counter[id0, iloc].astype(float)
                sigma[id0, iloc] = np.sqrt((nvals / n_years[id0])) /\
                    np.sqrt(n_years[id0])

        return sigma, counter, n_mags, n_times, n_years 

    
    def get_completeness_points(self, n_years, sigma, n_mags, n_time):
        '''Fits a bilinear model to each sigma-n_years combination
        in order to get the crossover point. The gradient of the first line
        must always be 1 / sqrt(T), but it is free for the other lines
        
        :param numpy.ndarray  n_years:
            Duration of each completeness time window
        
        :param numpy.ndarray sigma:
            Poisson variances of each time-magnitude combination 
        
        :param int n_mags:
            Number of magnitude bins
        
        :param int n_time: 
            Number of time bins
        
        :returns:
            * comp_time (Completeness duration)
            * gradient_2 (Gradient of second slope of piecewise linear fit)
            * model_line (Expected Poisson rate for data (only used for plot)
        '''
        time_vals = np.log10(n_years)
        sigma_vals = np.copy(sigma)
        valid_mapper = np.ones([n_time, n_mags], dtype=bool)
        valid_mapper[sigma_vals < 1E-9] = False
        comp_time = np.zeros(n_mags, dtype=float)
        gradient_2 = np.zeros(n_mags, dtype=float)
        model_line = np.zeros([n_time, n_mags], dtype=float)
        for iloc in range(0, n_mags):
            id0 = valid_mapper[:, iloc]
            if np.sum(id0) < 3:
                # Too few events for fitting a bilinear model!
                comp_time[iloc] = np.nan
                gradient_2[iloc] = np.nan
                model_line[:, iloc] = np.nan
            else:
                comp_time[iloc], gradient_2[iloc], model_line[id0, iloc] = \
                    self._fit_bilinear_to_stepp(time_vals[id0], 
                                                np.log10(sigma[id0, iloc]))
        return comp_time, gradient_2, model_line
        
   
    def _fit_bilinear_to_stepp(self, xdata, ydata, initial_values=None):
        '''Returns the residuals of a bilinear fit subject to the following 
        constraints: 1) gradient of slope 1 = 1 / sqrt(T)
                     2) Crossover (x_c) < 0
                     3) gradient 2 is always < 0
        
        :param numpy.ndarray xdata:
            x-value of the data set
        
        :param numpy.ndarray ydata:
            y-value of the data set
        
        :param list initial_values:
            For unit-testing allows the possibility to specify the initial
            values of the algorithm [slope_2, cross_over, intercept]
        
        :returns:
            * completeness_time: The duration of completeness of the bin
            * Gradient of the second slope
            * model_line: Expected Poisson model
        '''
        fixed_slope = -0.5 # f'(log10(T^-0.5)) === 0.5
        if isinstance(initial_values, list) or isinstance(initial_values,
            np.ndarray):
            x_0 = initial_values
        else:
            x_0 = [-1.0, xdata[len(xdata) / 2], xdata[0]]
        
        bnds = ((None, fixed_slope), (0.0, None), (None, None))
        result, _, convergence_info = \
            fmin_l_bfgs_b(get_bilinear_residuals_stepp, 
                          x_0,
                          args=(xdata, ydata, fixed_slope),
                          approx_grad=True,
                          bounds=bnds,
                          disp=0)

        if convergence_info['warnflag'] != 0:
            # Optimisation has failed to converge - print the reason why
            print convergence_info['task']
            return np.nan, np.nan, np.nan * np.ones(len(xdata))
        
        # Result contains three parameters = m_2, x_c, c_0
        # x_c is the crossover point (i.e. the completeness_time)
        # m_2 is the gradient of the latter slope
        # c_0 is the intercept - which helps locate the line at the data
        model_line = 10.0 ** (fixed_slope * xdata + result[2])
        completeness_time = 10. ** result[1]
        return completeness_time, result[0], model_line



