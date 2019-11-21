import lmfit
from uncertainties import ufloat
from pycqed.analysis import measurement_analysis as ma
from collections import OrderedDict
from mpl_toolkits.axes_grid1 import make_axes_locatable
import pycqed.analysis_v2.base_analysis as ba
import numpy as np
from pycqed.analysis.tools.data_manipulation import \
    populations_using_rate_equations
from pycqed.analysis.tools.plotting import set_xlabel, set_ylabel, plot_fit, \
    hsluv_anglemap45
import matplotlib.pyplot as plt
from pycqed.analysis.fitting_models import CosFunc, Cos_guess, \
    avoided_crossing_freq_shift
from pycqed.analysis_v2.simple_analysis import Basic2DInterpolatedAnalysis

from pycqed.analysis.analysis_toolbox import color_plot
import scipy.cluster.hierarchy as hcluster

from matplotlib import colors
from copy import deepcopy
from pycqed.analysis.tools.plot_interpolation import interpolate_heatmap
from pycqed.utilities import general as gen
from pycqed.instrument_drivers.meta_instrument.LutMans import flux_lutman as flm
from datetime import datetime
from pycqed.measurement.optimization import multi_targets_phase_offset

import logging

log = logging.getLogger(__name__)


class Chevron_Analysis(ba.BaseDataAnalysis):
    def __init__(self, ts: str = None, label=None,
                 ch_idx=0,
                 coupling='g', min_fit_amp=0, auto=True):
        """
        Analyzes a Chevron and fits the avoided crossing.

        Parameters
        ----------
        ts: str
            timestamp of the datafile
        label: str
            label to find the datafile (optional)
        ch_idx: int
            channel to use when fitting the avoided crossing
        coupling: Enum("g", "J1", "J2")
            used to label the avoided crossing and calculate related quantities
        min_fit_amp:
            minimal maplitude of the fitted cosine for each line cut.
            Oscillations with a smaller amplitude will be ignored in the fit
            of the avoided crossing.
        auto: bool
            if True run all parts of the analysis.

        """
        super().__init__(do_fitting=True)
        self.ts = ts
        self.label = label
        self.coupling = coupling
        self.ch_idx = ch_idx
        self.min_fit_amp = min_fit_amp
        if auto:
            self.run_analysis()

    def extract_data(self):
        self.raw_data_dict = OrderedDict()
        a = ma.MeasurementAnalysis(
            timestamp=self.ts, label=self.label, auto=False)
        a.get_naming_and_values_2D()
        a.finish()
        self.timestamps = [a.timestamp_string]
        self.raw_data_dict['timestamps'] = self.timestamps
        self.raw_data_dict['timestamp_string'] = a.timestamp
        for attr in ['sweep_points', 'sweep_points_2D', 'measured_values',
                     'parameter_names', 'parameter_units', 'value_names',
                     'value_units']:
            self.raw_data_dict[attr] = getattr(a, attr)
        self.raw_data_dict['folder'] = a.folder

    def process_data(self):
        self.proc_data_dict = OrderedDict()

        # select the relevant data
        x = self.raw_data_dict['sweep_points']
        t = self.raw_data_dict['sweep_points_2D']
        Z = self.raw_data_dict['measured_values'][self.ch_idx].T

        # fit frequencies to each individual cut (time trace)
        freqs = []
        freqs_std = []
        fit_results = []
        amps = []
        for xi, z in zip(x, Z.T):
            CosModel = lmfit.Model(CosFunc)
            CosModel.guess = Cos_guess
            pars = CosModel.guess(CosModel, z, t)
            fr = CosModel.fit(data=z, t=t, params=pars)
            amps.append(fr.params['amplitude'].value)
            freqs.append(fr.params['frequency'].value)
            freqs_std.append(fr.params['frequency'].stderr)
            fit_results.append(fr)
        # N.B. the fit results are not saved in self.fit_res as this would
        # bloat the datafiles.
        self.proc_data_dict['fit_results'] = np.array(fit_results)
        self.proc_data_dict['amp_fits'] = np.array(amps)
        self.proc_data_dict['freq_fits'] = np.array(freqs)
        self.proc_data_dict['freq_fits_std'] = np.array(freqs_std)

        # take a Fourier transform (nice for plotting)
        fft_data = abs(np.fft.fft(Z.T).T)
        fft_freqs = np.fft.fftfreq(len(t), d=t[1]-t[0])
        sort_vec = np.argsort(fft_freqs)

        fft_data_sorted = fft_data[sort_vec, :]
        fft_freqs_sorted = fft_freqs[sort_vec]
        self.proc_data_dict['fft_data_sorted'] = fft_data_sorted
        self.proc_data_dict['fft_freqs_sorted'] = fft_freqs_sorted

    def run_fitting(self):
        super().run_fitting()

        fit_mask = np.where(self.proc_data_dict['amp_fits'] > self.min_fit_amp)

        avoided_crossing_mod = lmfit.Model(avoided_crossing_freq_shift)
        # hardcoded guesses! Bad practice, needs a proper guess func
        avoided_crossing_mod.set_param_hint('a', value=3e9)
        avoided_crossing_mod.set_param_hint('b', value=-2e9)
        avoided_crossing_mod.set_param_hint('g', value=20e6, min=0)
        params = avoided_crossing_mod.make_params()

        self.fit_res['avoided_crossing'] = avoided_crossing_mod.fit(
            data=self.proc_data_dict['freq_fits'][fit_mask],
            flux=self.raw_data_dict['sweep_points'][fit_mask],
            params=params)

    def analyze_fit_results(self):
        self.proc_data_dict['quantities_of_interest'] = {}
        # Extract quantities of interest from the fit
        self.proc_data_dict['quantities_of_interest'] = {}
        qoi = self.proc_data_dict['quantities_of_interest']
        g = self.fit_res['avoided_crossing'].params['g']
        qoi['g'] = ufloat(g.value, g.stderr)

        self.coupling_msg = ''
        if self.coupling == 'J1':
            qoi['J1'] = qoi['g']
            qoi['J2'] = qoi['g']*np.sqrt(2)
            self.coupling_msg += r'Measured $J_1$ = {} MHz'.format(
                qoi['J1']*1e-6)+'\n'
            self.coupling_msg += r'Expected $J_2$ = {} MHz'.format(
                qoi['J2']*1e-6)
        elif self.coupling == 'J2':
            qoi['J1'] = qoi['g']/np.sqrt(2)
            qoi['J2'] = qoi['g']
            self.coupling_msg += r'Expected $J_1$ = {} MHz'.format(
                qoi['J1']*1e-6)+'\n'
            self.coupling_msg += r'Measured $J_2$ = {} MHz'.format(
                qoi['J2']*1e-6)
        else:
            self.coupling_msg += 'g = {}'.format(qoi['g'])

    def prepare_plots(self):
        for i, val_name in enumerate(self.raw_data_dict['value_names']):
            self.plot_dicts['chevron_{}'.format(val_name)] = {
                'plotfn': plot_chevron,
                'x': self.raw_data_dict['sweep_points'],
                'y': self.raw_data_dict['sweep_points_2D'],
                'Z': self.raw_data_dict['measured_values'][i].T,
                'xlabel': self.raw_data_dict['parameter_names'][0],
                'ylabel': self.raw_data_dict['parameter_names'][1],
                'zlabel': self.raw_data_dict['value_names'][i],
                'xunit': self.raw_data_dict['parameter_units'][0],
                'yunit': self.raw_data_dict['parameter_units'][1],
                'zunit': self.raw_data_dict['value_units'][i],
                'title': self.raw_data_dict['timestamp_string']+'\n' +
                'Chevron {}'.format(val_name)
            }

        self.plot_dicts['chevron_fft'] = {
            'plotfn': plot_chevron_FFT,
            'x': self.raw_data_dict['sweep_points'],
            'xunit': self.raw_data_dict['parameter_units'][0],
            'fft_freqs': self.proc_data_dict['fft_freqs_sorted'],
            'fft_data': self.proc_data_dict['fft_data_sorted'],
            'freq_fits': self.proc_data_dict['freq_fits'],
            'freq_fits_std': self.proc_data_dict['freq_fits_std'],
            'fit_res': self.fit_res['avoided_crossing'],
            'coupling_msg': self.coupling_msg,
            'title': self.raw_data_dict['timestamp_string']+'\n' +
            'Fourier transform of Chevron'}


def plot_chevron(x, y, Z, xlabel, xunit, ylabel, yunit,
                 zlabel, zunit,
                 title, ax, **kw):
    colormap = ax.pcolormesh(x, y, Z, cmap='viridis',  # norm=norm,
                             linewidth=0, rasterized=True,
                             # assumes digitized readout
                             vmin=0, vmax=1)
    set_xlabel(ax, xlabel, xunit)
    set_ylabel(ax, ylabel, yunit)
    ax.set_title(title)

    ax_divider = make_axes_locatable(ax)
    cax = ax_divider.append_axes('right', size='5%', pad='2%')
    cbar = plt.colorbar(colormap, cax=cax, orientation='vertical')
    cax.set_ylabel('L1 (%)')

    set_ylabel(cax, zlabel, zunit)


def plot_chevron_FFT(x, xunit,  fft_freqs, fft_data, freq_fits, freq_fits_std,
                     fit_res, coupling_msg, title, ax, **kw):

    colormap = ax.pcolormesh(x,
                             fft_freqs, fft_data, cmap='viridis',  # norm=norm,
                             linewidth=0, rasterized=True, vmin=0, vmax=5)

    ax.errorbar(x=x, y=freq_fits, yerr=freq_fits_std, ls='--', c='r', alpha=.5,
                label='Extracted freqs')
    x_fine = np.linspace(x[0], x[-1], 200)
    plot_fit(x, fit_res, ax=ax, c='C1', label='Avoided crossing fit', ls=':')

    set_xlabel(ax, 'Flux bias', xunit)
    set_ylabel(ax, 'Frequency', 'Hz')
    ax.legend(loc=(1.05, .7))
    ax.text(1.05, 0.5, coupling_msg, transform=ax.transAxes)


class Conditional_Oscillation_Heatmap_Analysis(Basic2DInterpolatedAnalysis):
    """
    Intended for the analysis of CZ tuneup (theta_f, lambda_2) heatmaps
    The data can be from an experiment or simulation
    """
    def __init__(self,
                t_start: str = None,
                t_stop: str = None,
                label: str = '',
                data_file_path: str = None,
                close_figs: bool = True,
                options_dict: dict = None,
                extract_only: bool = False,
                do_fitting: bool = False,
                auto: bool = True,
                interp_method: str = 'linear',
                plt_orig_pnts: bool = True,
                plt_contour_phase: bool = True,
                plt_contour_L1: bool = False,
                plt_optimal_values: bool = True,
                plt_optimal_values_max: int = np.inf,
                plt_clusters: bool = True,
                clims: dict = None,
                find_local_optimals: bool = True,
                cluster_from_interp: bool = False,

                rescore_spiked_optimals: bool = False,
                plt_optimal_waveforms_all: bool = False,
                plt_optimal_waveforms: bool = False,
                waveform_flux_lm_name: str = None,

                target_cond_phase: float = 180.,
                single_q_phase_offset: bool = False):

        self.plt_orig_pnts = plt_orig_pnts
        self.plt_contour_phase = plt_contour_phase
        self.plt_contour_L1 = plt_contour_L1
        self.plt_optimal_values = plt_optimal_values
        self.plt_optimal_values_max = plt_optimal_values_max
        self.plt_clusters = plt_clusters

        self.clims = clims

        self.find_local_optimals = find_local_optimals
        self.cluster_from_interp = cluster_from_interp

        self.rescore_spiked_optimals = rescore_spiked_optimals
        self.plt_optimal_waveforms = plt_optimal_waveforms
        self.plt_optimal_waveforms_all = plt_optimal_waveforms_all
        self.waveform_flux_lm_name = waveform_flux_lm_name

        self.target_cond_phase = target_cond_phase
        # Used when applying Pi pulses to check if both single qubits
        # have the same phase as in the ideal case
        self.single_q_phase_offset = single_q_phase_offset

        self._generate_waveform = False
        if plt_optimal_waveforms or \
                plt_optimal_waveforms_all or \
                rescore_spiked_optimals:
            self._generate_waveform = True
            assert waveform_flux_lm_name is not None

        cost_func_Names = {'Cost func', 'Cost func.', 'cost func',
        'cost func.', 'cost function', 'Cost function', 'Cost function value'}
        L1_names = {'L1', 'Leakage'}
        ms_names = {'missing fraction', 'Missing fraction', 'missing frac',
            'missing frac.', 'Missing frac', 'Missing frac.'}
        cond_phase_names = {'Cond phase', 'Cond. phase', 'Conditional phase',
            'cond phase', 'cond. phase', 'conditional phase'}
        offset_diff_names = {'offset difference', 'offset diff',
            'offset diff.', 'Offset difference', 'Offset diff',
            'Offset diff.'}

        # also account for possible underscores instead of a spaces between words
        allNames = [cost_func_Names, L1_names, ms_names, cond_phase_names,
            offset_diff_names]
        [self.cost_func_Names, self.L1_names, self.ms_names, self.cond_phase_names,
            self.offset_diff_names] = \
            [names.union({name.replace(' ', '_') for name in names})
                for names in allNames]

        cost_func_Names = {'Cost func', 'Cost func.', 'cost func',
        'cost func.', 'cost function', 'Cost function', 'Cost function value'}
        L1_names = {'L1', 'Leakage'}
        ms_names = {'missing fraction', 'Missing fraction', 'missing frac',
            'missing frac.', 'Missing frac', 'Missing frac.'}
        cond_phase_names = {'Cond phase', 'Cond. phase', 'Conditional phase',
            'cond phase', 'cond. phase', 'conditional phase'}
        offset_diff_names = {'offset difference', 'offset diff',
            'offset diff.', 'Offset difference', 'Offset diff',
            'Offset diff.'}

        # also account for possible underscores instead of a spaces between words
        allNames = [cost_func_Names, L1_names, ms_names, cond_phase_names,
            offset_diff_names]
        [self.cost_func_Names, self.L1_names, self.ms_names, self.cond_phase_names,
            self.offset_diff_names] = \
            [names.union({name.replace(' ', '_') for name in names})
                for names in allNames]

        super().__init__(
            t_start=t_start,
            t_stop=t_stop,
            label=label,
            data_file_path=data_file_path,
            close_figs=close_figs,
            options_dict=options_dict,
            extract_only=extract_only,
            do_fitting=do_fitting,
            auto=auto,
            interp_method=interp_method
        )

    def prepare_plots(self):
        # assumes that value names are unique in an experiment
        super().prepare_plots()
        anglemap = hsluv_anglemap45

        for i, val_name in enumerate(self.proc_data_dict['value_names']):

            zlabel = '{} ({})'.format(val_name,
                                      self.proc_data_dict['value_units'][i])
            self.plot_dicts[val_name] = {
                'ax_id': val_name,
                'plotfn': color_plot,
                'x': self.proc_data_dict['x_int'],
                'y': self.proc_data_dict['y_int'],
                'z': self.proc_data_dict['interpolated_values'][i],
                'xlabel': self.proc_data_dict['xlabel'],
                'x_unit': self.proc_data_dict['xunit'],
                'ylabel': self.proc_data_dict['ylabel'],
                'y_unit': self.proc_data_dict['yunit'],
                'zlabel': zlabel,
                'title': '{}\n{}'.format(
                    self.timestamp, self.proc_data_dict['measurementstring'])
            }

            if self.plt_orig_pnts:
                self.plot_dicts[val_name + '_non_interpolated'] = {
                    'ax_id': val_name,
                    'plotfn': scatter_pnts_overlay,
                    'x': self.proc_data_dict['x'],
                    'y': self.proc_data_dict['y']
                }

            if self.proc_data_dict['value_units'][i] == 'deg':
                self.plot_dicts[val_name]['cbarticks'] = np.arange(0., 360.1, 45)
                self.plot_dicts[val_name]['cmap_chosen'] = anglemap
                self.plot_dicts[val_name]['clim'] = [0., 360.]

            if self.clims is not None and val_name in self.clims.keys():
                self.plot_dicts[val_name]['clim'] = self.clims[val_name]

            if self.plt_contour_phase:
                # Find index of Conditional Phase
                z_cond_phase = None
                for j, val_name_j in enumerate(self.proc_data_dict['value_names']):
                    pass
                    if val_name_j in self.cond_phase_names:
                        z_cond_phase = self.proc_data_dict['interpolated_values'][j]
                        break

                if z_cond_phase is not None:
                    self.plot_dicts[val_name + '_cond_phase_contour'] = {
                        'ax_id': val_name,
                        'plotfn': contour_overlay,
                        'x': self.proc_data_dict['x_int'],
                        'y': self.proc_data_dict['y_int'],
                        'z': z_cond_phase,
                        'colormap': anglemap,
                        'cyclic_data': True,
                        'contour_levels': [90, 180, 270],
                        'vlim': (0, 360)
                    }
                else:
                    log.warning('No data found named {}'.format(self.cond_phase_names))

            if self.plt_contour_L1:
                # Find index of Leakage or Missing Fraction
                z_L1 = None
                for j, val_name_j in enumerate(self.proc_data_dict['value_names']):
                    if val_name_j in self.L1_names or val_name_j in self.ms_names:
                        z_L1 = self.proc_data_dict['interpolated_values'][j]
                        break

                if z_L1 is not None:
                    vlim = (self.proc_data_dict['interpolated_values'][j].min(),
                        self.proc_data_dict['interpolated_values'][j].max())

                    contour_levels = np.array([1, 5, 10])
                    # Leakage is estimated as (Missing fraction/2)
                    contour_levels = contour_levels if \
                        self.proc_data_dict['value_names'][j] in self.L1_names \
                        else 2 * contour_levels

                    self.plot_dicts[val_name + '_L1_contour'] = {
                        'ax_id': val_name,
                        'plotfn': contour_overlay,
                        'x': self.proc_data_dict['x_int'],
                        'y': self.proc_data_dict['y_int'],
                        'z': z_L1,
                        # 'unit': self.proc_data_dict['value_units'][j],
                        'contour_levels': contour_levels,
                        'vlim': vlim,
                        'colormap': 'hot',
                        'linestyles': 'dashdot'
                    }
                else:
                    log.warning('No data found named {}'.format(self.L1_names))

            if val_name in set().union(self.L1_names).union(self.ms_names)\
                    .union(self.offset_diff_names):
                self.plot_dicts[val_name]['cmap_chosen'] = 'hot'

            if self.plt_optimal_values and \
                    val_name in self.cost_func_Names:
                    self.plot_dicts[val_name + '_optimal_pars'] = {
                        'ax_id': val_name,
                        'ypos': -0.25,
                        'xpos': 0,
                        'plotfn': self.plot_text,
                        'box_props': 'fancy',
                        'line_kws': {'alpha': 0},
                        'text_string': self.get_readable_optimals(optimal_end=self.plt_optimal_values_max),
                        'horizontalalignment': 'left',
                        'verticalaligment': 'top',
                        'fontsize': 14
                    }

            if self.plt_clusters:
                self.plot_dicts[val_name + '_clusters'] = {
                    'ax_id': val_name,
                    'plotfn': scatter_pnts_overlay,
                    'x': self.proc_data_dict['clusters_pnts_x'],
                    'y': self.proc_data_dict['clusters_pnts_y'],
                    'color': None,
                    'edgecolors': None if self.cluster_from_interp else 'black',
                    'marker': 'o',
                    # 'linewidth': 1,
                    'c': self.proc_data_dict['clusters_pnts_colors']
                }
            if self.plt_optimal_values:
                self.plot_dicts[val_name + '_optimal_pnts_annotate'] = {
                    'ax_id': val_name,
                    'plotfn': annotate_pnts,
                    'txt': np.arange(np.size(self.proc_data_dict['x_optimal'])),
                    'x': self.proc_data_dict['x_optimal'],
                    'y': self.proc_data_dict['y_optimal']
                }

        if self.plt_optimal_waveforms_all:
            try:
                # Plot all together for comparison
                ax_id = 'waveform_optimal_all'
                self.plot_dicts[ax_id] = {
                    'ax_id': ax_id,
                    'plotfn': self.plot_line,
                    'yvals': self.proc_data_dict['optimal_waveforms'],
                    'xvals': self.proc_data_dict['optimal_waveforms_time'],
                    'xlabel': 't',
                    'x_unit': 's',
                    'title': '{}\n{}\nOptimal waveforms'.format(
                        self.timestamp,
                        self.proc_data_dict['measurementstring']),
                    'marker': '.',
                    'do_legend': True,
                    'legend_ncol': 2
                }
            except Exception as e:
                log.error('Could not plot all waveforms.')
                log.error(e)
        if self.plt_optimal_waveforms:
            try:
                # Plot individual waveforms
                for opt_id, optimal_waveform in enumerate(self.proc_data_dict['optimal_waveforms']):
                    ax_id = 'waveform_optimal_{}'.format(opt_id)
                    self.plot_dicts[ax_id] = {
                        'ax_id': ax_id,
                        'plotfn': self.plot_line,
                        'yvals': self.proc_data_dict['optimal_waveforms'][opt_id],
                        'xvals': self.proc_data_dict['optimal_waveforms_time'][opt_id],
                        'xlabel': 't',
                        'x_unit': 's',
                        'title': '{}\n{}\nOptimal #{} waveform'.format(
                            self.timestamp,
                            self.proc_data_dict['measurementstring'],
                            opt_id),
                        'marker': '.'
                    }
            except Exception as e:
                log.error('Error plotting a waveform.')
                log.error(e)

    def process_data(self):
        self.proc_data_dict = deepcopy(self.raw_data_dict)

        phase_q0_name = 'phase_q0'
        phase_q1_name = 'phase_q1'
        if self.single_q_phase_offset and {phase_q0_name, phase_q1_name} <= set(self.proc_data_dict['value_names']):
            self.proc_data_dict['value_names'].append('phase_q1 - phase_q0')
            self.proc_data_dict['value_units'].append('deg')
            phase_q0 = self.proc_data_dict['measured_values'][self.proc_data_dict['value_names'].index(phase_q0_name)]
            phase_q1 = self.proc_data_dict['measured_values'][self.proc_data_dict['value_names'].index(phase_q1_name)]
            self.proc_data_dict['measured_values'] = np.vstack((self.proc_data_dict['measured_values'], (phase_q1 - phase_q0) % 360))

        vln = self.proc_data_dict['value_names']
        measured_vals = self.proc_data_dict['measured_values']
        vlu = self.proc_data_dict['value_units']

        self.proc_data_dict['interpolated_values'] = []
        for i in range(len(self.proc_data_dict['value_names'])):
            if self.proc_data_dict['value_units'][i] == 'deg':
                interp_method = 'deg'
            else:
                interp_method = self.interp_method

            x_int, y_int, z_int = interpolate_heatmap(
                self.proc_data_dict['x'],
                self.proc_data_dict['y'],
                self.proc_data_dict['measured_values'][i],
                interp_method=interp_method)
            self.proc_data_dict['interpolated_values'].append(z_int)

            # if self.proc_data_dict['value_names'][i] in self.cost_func_Names:
            #     # Find the optimal point(s)
            #     x = self.proc_data_dict['x']
            #     y = self.proc_data_dict['y']
            #     z = self.proc_data_dict['measured_values'][i]

        interp_vals = self.proc_data_dict['interpolated_values']
        self.proc_data_dict['x_int'] = x_int
        self.proc_data_dict['y_int'] = y_int

        # Processing for optimal points
        if not self.cluster_from_interp:
            where = [(name in self.cost_func_Names) for name in vln]
            cost_func_indxs = np.where(where)[0][0]
            cost_func = measured_vals[cost_func_indxs]

            try:
                where = [(name in self.cond_phase_names) for name in vln]
                cond_phase_indx = np.where(where)[0][0]
                cond_phase_arr = measured_vals[cond_phase_indx]
            except Exception:
                # Ignore if was not measured
                pass

            try:
                where = [(name in self.L1_names) for name in vln]
                L1_indx = np.where(where)[0][0]
                L1_arr = measured_vals[L1_indx]
            except Exception:
                # Ignore if was not measured
                pass

            theta_f_arr = self.proc_data_dict['x']
            lambda_2_arr = self.proc_data_dict['y']

            extract_optimals_from = 'measured_values'
        else:
            where = [(name in self.cost_func_Names) for name in vln]
            cost_func_indxs = np.where(where)[0][0]
            cost_func = interp_vals[cost_func_indxs]
            cost_func = interp_to_1D_arr(z_int=cost_func)

            where = [(name in self.cond_phase_names) for name in vln]
            cond_phase_indx = np.where(where)[0][0]
            cond_phase_arr = interp_vals[cond_phase_indx]
            cond_phase_arr = interp_to_1D_arr(z_int=cond_phase_arr)

            where = [(name in self.L1_names) for name in vln]
            L1_indx = np.where(where)[0][0]
            L1_arr = interp_vals[L1_indx]
            L1_arr = interp_to_1D_arr(z_int=L1_arr)

            theta_f_arr = self.proc_data_dict['x_int']
            lambda_2_arr = self.proc_data_dict['y_int']

            theta_f_arr, lambda_2_arr = interp_to_1D_arr(x_int=theta_f_arr,
                y_int=lambda_2_arr)

            extract_optimals_from = 'interpolated_values'

        if not self.find_local_optimals:
            optimal_idxs = np.array([cost_func.argmin()])
            clusters_by_indx = np.array([optimal_idxs])
        else:
            optimal_idxs, clusters_by_indx = get_optimal_pnts_indxs(
                theta_f_arr=theta_f_arr,
                lambda_2_arr=lambda_2_arr,
                cond_phase_arr=cond_phase_arr,
                L1_arr=L1_arr,
                target_phase=self.target_cond_phase
            )

        if self.cluster_from_interp:
            x_arr = theta_f_arr
            y_arr = lambda_2_arr
        else:
            x_arr = self.proc_data_dict['x']
            y_arr = self.proc_data_dict['y']

        # Generate waveforms for best optimal_pnts
        if self._generate_waveform:
            try:
                timestamp = self.raw_data_dict['timestamps'][0]
                # In case the code breaks and the dummy fluxlutman is not closed
                # We give it a "random" time based name
                time_string = datetime.now().strftime('%Y%d%m_%H%M%S_%f')
                fluxlutman = flm.HDAWG_Flux_LutMan('flux_lm_auto_{}'.format(time_string))
                ignore_pars = {'AWG', 'instr_distortion_kernel', 'instr_partner_lutman'}
                if self.waveform_flux_lm_name is None:
                    waveform_flux_lm_name = 'flux_lm'
                else:
                    waveform_flux_lm_name = self.waveform_flux_lm_name
                gen.load_settings_onto_instrument_v2(
                    fluxlutman,
                    load_from_instr=waveform_flux_lm_name,
                    timestamp=timestamp,
                    ignore_pars=ignore_pars)
                x_par_name = self.proc_data_dict['xlabel']
                y_par_name = self.proc_data_dict['ylabel']
                # Maybe there is a better way to figure out which gate was simulated
                which_gates = {'NE', 'SE', 'NW', 'SW'}
                which_gate = x_par_name[-2:]
                if which_gate not in which_gates:
                    which_gate = y_par_name[-2:]
                # We don't simulate this
                fluxlutman.set('cz_phase_corr_length_{}'.format(which_gate), 0)
                waveforms = []
                times = []
                spiked_optimals = []

                for ii in range(np.size(optimal_idxs)):
                    fluxlutman.set(x_par_name, x_arr[optimal_idxs][ii])
                    fluxlutman.set(y_par_name, y_arr[optimal_idxs][ii])

                    fluxlutman.generate_standard_waveforms()
                    waveform = fluxlutman._gen_cz(which_gate=which_gate)
                    waveforms.append(waveform)
                    time = np.cumsum(np.full(np.size(waveform), 1 / fluxlutman.sampling_rate()))
                    times.append(time)
                    # NB: it is assumed 'No AWG present, returning unity scale factor.'
                    # NB2: this sorting very empirical
                    waveform_max = np.max(waveform)

                    # spiked_optimals.append(0)  # switch to this line to ignore spikes downscoring
                    spiked_optimals.append(np.any(waveform > 1.25) * (waveform_max - np.average(np.abs(waveform))) / waveform_max)

                fluxlutman.close()

            except Exception as e:
                log.warning('Could not generate optimal_pnts wave forms.')
                log.warning(e)

            if self.rescore_spiked_optimals:

                sort_indxs = np.argsort(spiked_optimals)
                optimal_idxs = np.array(optimal_idxs)[sort_indxs]

                clusters_by_indx = np.array(clusters_by_indx)[sort_indxs]
                waveforms = np.array(waveforms)[sort_indxs]
                times = np.array(times)[sort_indxs]
            # Add qoi in the proc_data_dict
            self.proc_data_dict['optimal_waveforms'] = waveforms
            self.proc_data_dict['optimal_waveforms_time'] = times
            self.proc_data_dict['spiked_optimals'] = spiked_optimals

        clusters_pnts_x = np.array([])
        clusters_pnts_y = np.array([])
        clusters_pnts_colors = np.array([])

        for l, cluster_by_indx in enumerate(clusters_by_indx):
            clusters_pnts_x = np.concatenate(
                (clusters_pnts_x, x_arr[cluster_by_indx]))
            clusters_pnts_y = np.concatenate(
                (clusters_pnts_y, y_arr[cluster_by_indx]))
            clusters_pnts_colors = np.concatenate(
                (clusters_pnts_colors,
                np.full(np.shape(cluster_by_indx)[0], l)))

        self.proc_data_dict['optimal_idxs'] = optimal_idxs

        self.proc_data_dict['clusters_pnts_x'] = clusters_pnts_x
        self.proc_data_dict['clusters_pnts_y'] = clusters_pnts_y
        self.proc_data_dict['clusters_pnts_colors'] = clusters_pnts_colors

        self.proc_data_dict['x_optimal'] = x_arr[optimal_idxs]
        self.proc_data_dict['y_optimal'] = y_arr[optimal_idxs]

        optimal_pars_values = []
        for x, y in zip(self.proc_data_dict['x_optimal'], self.proc_data_dict['y_optimal']):
            optimal_pars_values.append({self.proc_data_dict['xlabel']: x,
                                        self.proc_data_dict['ylabel']: y})
        self.proc_data_dict['optimal_pars_values'] = optimal_pars_values

        self.proc_data_dict['optimal_pars_units'] = {
            self.proc_data_dict['xlabel']: self.proc_data_dict['xunit'],
            self.proc_data_dict['ylabel']: self.proc_data_dict['yunit']
        }
        # vlu = self.proc_data_dict['value_units']
        # optimal_measured_values = {}
        # optimal_measured_units = {}
        # for k, quantity_arr in enumerate(self.proc_data_dict[extract_optimals_from]):
        #     optimal_measured_values[vln[k]] = np.ravel(quantity_arr)[optimal_idxs]
        #     optimal_measured_units[vln[k]] = vlu[k]
        # self.proc_data_dict['optimal_measured_values'] = optimal_measured_values
        # self.proc_data_dict['optimal_measured_units'] = optimal_measured_units

        optimal_measured_values = []
        optimal_measured_units = []
        mvs = self.proc_data_dict[extract_optimals_from]
        for optimal_idx in optimal_idxs:
            optimal_measured_values.append({name: np.ravel(mvs[ii])[optimal_idx] for ii, name in enumerate(vln)})
        optimal_measured_units = {name: vlu[ii] for ii, name in enumerate(vln)}
        self.proc_data_dict['optimal_measured_values'] = optimal_measured_values
        self.proc_data_dict['optimal_measured_units'] = optimal_measured_units

        # Save quantities of interest
        save_these = {
            'optimal_pars_values',
            'optimal_pars_units',
            'optimal_measured_values',
            'optimal_measured_units',
            'spiked_optimals',
            'optimal_waveforms',
            'optimal_waveforms_time',
            'clusters_pnts_y',
            'clusters_pnts_x',
            'clusters_pnts_colors'
        }
        pdd = self.proc_data_dict
        quantities_of_interest = dict()
        for save_this in save_these:
            if save_this in pdd.keys():
                if pdd[save_this] is not None:
                    quantities_of_interest[save_this] = pdd[save_this]
        if bool(quantities_of_interest):
            self.proc_data_dict['quantities_of_interest'] = quantities_of_interest

    def plot_text(self, pdict, axs):
        """
        Helper function that adds text to a plot
        Overriding here in order to make the text bigger
        and put it below the the cost function figure
        """
        pfunc = getattr(axs, pdict.get('func', 'text'))
        plot_text_string = pdict['text_string']
        plot_xpos = pdict.get('xpos', .98)
        plot_ypos = pdict.get('ypos', .98)
        fontsize = pdict.get('fontsize', 10)
        verticalalignment = pdict.get('verticalalignment', 'top')
        horizontalalignment = pdict.get('horizontalalignment', 'left')
        fontdict = {
            'horizontalalignment': horizontalalignment,
            'verticalalignment': verticalalignment
        }

        if fontsize is not None:
            fontdict['fontsize'] = fontsize

        # fancy box props is based on the matplotlib legend
        box_props = pdict.get('box_props', 'fancy')
        if box_props == 'fancy':
            box_props = self.fancy_box_props

        # pfunc is expected to be ax.text
        pfunc(x=plot_xpos, y=plot_ypos, s=plot_text_string,
              transform=axs.transAxes,
              bbox=box_props, fontdict=fontdict)

    def get_readable_optimals(self,
            optimal_pars_values=None,
            optimal_measured_values=None,
            optimal_start: int = 0,
            optimal_end: int = np.inf,
            sig_digits=4):
        if not optimal_pars_values:
            optimal_pars_values = self.proc_data_dict['optimal_pars_values']
        if not optimal_measured_values:
            optimal_measured_values = self.proc_data_dict['optimal_measured_values']

        optimals_max = len(optimal_pars_values)
        spiked = self.proc_data_dict['spiked_optimals'] if 'spiked_optimals'\
            in self.proc_data_dict else np.full(optimals_max, False)
        string = ''
        for opt_idx in range(optimal_start, int(min(optimal_end + 1, optimals_max))):
            string += '========================\n'
            string += 'Optimal #{}{}\n'.format(opt_idx, '[Spiked]' if spiked[opt_idx] else '')
            string += '========================\n'
            for pv_name, pv_value in optimal_pars_values[opt_idx].items():
                string += '{} = {:.{sig_digits}g} {}\n'.format(pv_name, pv_value, self.proc_data_dict['optimal_pars_units'][pv_name], sig_digits=sig_digits)
            string += '------------\n'
            if self.cluster_from_interp and optimal_pars_values is self.proc_data_dict['optimal_pars_values']:
                string += '[!!! Interpolated values !!!]\n'
            for mv_name, mv_value in optimal_measured_values[opt_idx].items():
                string += '{} = {:.{sig_digits}g} {}\n'.format(mv_name, mv_value, self.proc_data_dict['optimal_measured_units'][mv_name], sig_digits=sig_digits)
        return string


def scatter_pnts_overlay(
        x,
        y,
        fig=None,
        ax=None,
        transpose=False,
        color='w',
        edgecolors='gray',
        linewidth=0.5,
        marker='.',
        s=None,
        c=None,
        **kw):
    """
    Adds a scattered overlay of the provided data points
    x, and y are lists.
    Args:
        x (array [shape: n*1]):     x data
        y (array [shape: m*1]):     y data
        fig (Object):
            figure object
    """
    if ax is None:
        fig, ax = plt.subplots()

    if transpose:
        log.debug('Inverting x and y axis for non-interpolated points')
        ax.scatter(y, x, marker=marker,
            color=color, edgecolors=edgecolors, linewidth=linewidth, s=s, c=c)
    else:
        ax.scatter(x, y, marker=marker,
            color=color, edgecolors=edgecolors, linewidth=linewidth, s=s, c=c)

    return fig, ax


def contour_overlay(x, y, z, colormap, transpose=False,
        contour_levels=[90, 180, 270], vlim=(0, 360), fig=None,
        linestyles='dashed',
        cyclic_data=False,
        ax=None, **kw):
    """
    x, and y are lists, z is a matrix with shape (len(x), len(y))
    N.B. The contour overaly suffers from artifacts sometimes
    Args:
        x (array [shape: n*1]):     x data
        y (array [shape: m*1]):     y data
        z (array [shape: n*m]):     z data for the contour
        colormap (matplotlib.colors.Colormap or str): colormap to be used
        unit (str): 'deg' is a special case
        vlim (tuple(vmin, vmax)): required for the colormap nomalization
        fig (Object):
            figure object
    """
    if ax is None:
        fig, ax = plt.subplots()

    vmin = vlim[0]
    vmax = vlim[-1]

    norm = colors.Normalize(vmin=vmin, vmax=vmax, clip=True)
    linewidth = 2
    fontsize = 'smaller'

    if transpose:
        y_tmp = np.copy(y)
        y = np.copy(x)
        x = y_tmp
        z = np.transpose(z)

    if cyclic_data:
        # Avoid contour plot artifact for cyclic data by removing the
        # data half way to the cyclic boundary
        minz = (vmin + np.min(contour_levels)) / 2
        maxz = (vmax + np.max(contour_levels)) / 2
        z = np.copy(z)  # don't change the original data
        z[(z < minz) | (z > maxz)] = np.nan

    c = ax.contour(x, y, z,
        levels=contour_levels, linewidths=linewidth, cmap=colormap,
        norm=norm, linestyles=linestyles)
    ax.clabel(c, fmt='%.1f', inline='True', fontsize=fontsize)

    return fig, ax


def annotate_pnts(txt, x, y,
        textcoords='offset points',
        ha='center',
        va='center',
        xytext=(0, 0),
        bbox=dict(boxstyle='circle, pad=0.2', fc='white', alpha=0.7),
        arrowprops=None,
        transpose=False,
        fig=None,
        ax=None,
        **kw):
    """
    A handy for loop for the ax.annotate
    """
    if ax is None:
        fig, ax = plt.subplots()

    if transpose:
        y_tmp = np.copy(y)
        y = np.copy(x)
        x = y_tmp

    for i, text in enumerate(txt):
            ax.annotate(text,
                xy=(x[i], y[i]),
                textcoords=textcoords,
                ha=ha,
                va=va,
                xytext=xytext,
                bbox=bbox)
    return fig, ax


def get_optimal_pnts_indxs(
        theta_f_arr,
        lambda_2_arr,
        cond_phase_arr,
        L1_arr,
        target_phase=180,
        phase_thr=5,
        L1_thr=0.3,
        clustering_thr=10,
        tolerances=[1, 2, 3]):
    """
    target_phase and low L1 need to match roughtly cost function's minimums

    Args:
    target_phase: unit = deg
    phase_thr: unit = deg, only points with cond phase below this threshold
        will be used for clustering

    L1_thr: unit = %, only points with leakage below this threshold
        will be used for clustering

    clustering_thr: unit = deg, represents distance between points on the
        landscape (lambda_2 gets normalized to [0, 360])

    tolerances: phase_thr and L1_thr will be multiplied by the values in
    this list successively if no points are found for the first element
    in the list
    """
    x = np.array(theta_f_arr)
    y = np.array(lambda_2_arr)

    # Normalize distance
    x_norm = x / 360.
    y_norm = y / (2 * np.pi)

    # Select points based low leakage and on how close to the
    # target_phase they are
    for tol in tolerances:
        phase_thr *= tol
        L1_thr *= tol
        cond_phase_dev_f = multi_targets_phase_offset(target_phase, 2 * target_phase)
        # np.abs(cond_phase_arr - target_phase)
        cond_phase_abs_diff = cond_phase_dev_f(cond_phase_arr)
        sel = cond_phase_abs_diff <= phase_thr
        sel = sel * (L1_arr <= L1_thr)
        # sel = sel * (x_norm > y_norm)
        # Exclude point on the boundaries
        sel = sel * (x < np.max(x)) * (x > np.min(x)) * (y < np.max(y)) * (y > np.min(y))
        selected_points_indxs = np.where(sel)[0]
        if np.size(selected_points_indxs) == 0:
            log.warning('No optimal points found with  |target_phase - cond phase| < {} and L1 < {}.'.format(
                phase_thr, L1_thr))
            if tol == tolerances[-1]:
                return np.array([], dtype=int), np.array([], dtype=int)
            log.warning('Increasing tolerance for phase_thr and L1 to x{}.'.format(tol + 1))
        elif np.size(selected_points_indxs) == 1:
            return np.array(selected_points_indxs), np.array([selected_points_indxs])
        else:
            x_filt = x_norm[selected_points_indxs]
            y_filt = y_norm[selected_points_indxs]
            break

    # Cluster points based on distance
    x_y_filt = np.transpose([x_filt, y_filt])
    thresh = clustering_thr / 360.
    clusters = hcluster.fclusterdata(x_y_filt, thresh, criterion="distance")

    cluster_id_min = np.min(clusters)
    cluster_id_max = np.max(clusters)
    clusters_by_indx = []
    optimal_idxs = []
    av_L1 = []
    # av_cp_diff = []
    # neighbors_num = []
    for cluster_id in range(cluster_id_min, cluster_id_max + 1):

        cluster_indxs = np.where(clusters == cluster_id)
        indxs_in_orig_array = selected_points_indxs[cluster_indxs]
        L1_av_around = [av_around(x_norm, y_norm, L1_arr, idx, thresh * 1.5)[0] for idx in indxs_in_orig_array]
        min_idx = np.argmin(L1_av_around)

        optimal_idx = indxs_in_orig_array[min_idx]
        optimal_idxs.append(optimal_idx)

        clusters_by_indx.append(indxs_in_orig_array)

        # sq_dist = (x_norm - x_norm[optimal_idx])**2 + (y_norm - y_norm[optimal_idx])**2
        # neighbors_indx = np.where(sq_dist <= (thresh * 1.5)**2)
        # neighbors_num.append(np.size(neighbors_indx))
        # av_cp_diff.append(np.average(cond_phase_abs_diff[neighbors_indx]))
        # av_L1.append(np.average(L1_arr[neighbors_indx]))

        av_L1.append(L1_av_around[min_idx])

    av_L1_w = 1.
    # This would be biased towards the original adpative sampling cost func
    # neighbors_num_w = 0.
    # Very few points will actually be precisely on the target phase contour
    # Therefore not used
    # av_cp_diff_w = 0.
    # low leakage is best
    w1 = av_L1_w * np.array(av_L1) / np.max(av_L1) / np.array([it for it in map(np.size, clusters_by_indx)])
    # value more the points with more neighbors as a confirmation of
    # low leakage area and also scores less points near the boundaries
    # of the sampling area
    # w2 = neighbors_num_w * (1 - np.flip(np.array(neighbors_num) / np.max(neighbors_num)))
    # low phase diff is best
    # w3 = av_cp_diff_w * np.array(av_cp_diff) / np.max(av_cp_diff)

    sort_by = w1  # + w2 + w3

    if np.any(np.array(sort_by) != np.sort(sort_by)):
        log.debug(' Optimal points rescored based on low leakage areas.')

    optimal_idxs = np.array(optimal_idxs)[np.argsort(sort_by)]
    clusters_by_indx = np.array(clusters_by_indx)[np.argsort(sort_by)]

    return optimal_idxs, clusters_by_indx


def av_around(x, y, z, idx, radius):
    sq_dist = (x - x[idx])**2 + (y - y[idx])**2
    neighbors_indx = np.where(sq_dist <= radius**2)
    return np.average(z[neighbors_indx]), neighbors_indx


def interp_to_1D_arr(x_int=None, y_int=None, z_int=None, slice_above_len=None):
    """
    Turns interpolated heatmaps into linear 1D array
    Intended for data reshaping for get_optimal_pnts_indxs
    """
    if slice_above_len is not None:
        if x_int is not None:
            size = np.size(x_int)
            slice_step = np.int(np.ceil(size / slice_above_len))
            x_int = np.array(x_int)[::slice_step]
        if y_int is not None:
            size = np.size(y_int)
            slice_step = np.int(np.ceil(size / slice_above_len))
            y_int = np.array(y_int)[::slice_step]
        if z_int is not None:
            size_0 = np.shape(z_int)[0]
            size_1 = np.shape(z_int)[1]
            slice_step_0 = np.int(np.ceil(size_0 / slice_above_len))
            slice_step_1 = np.int(np.ceil(size_1 / slice_above_len))
            z_int = np.array(z_int)[::slice_step_0, ::slice_step_1]

    if x_int is not None and y_int is not None and z_int is not None:
        x_int_1D = np.ravel(np.repeat([x_int], np.size(y_int), axis=0))
        y_int_1D = np.ravel(np.repeat([y_int], np.size(x_int), axis=1))
        z_int_1D = np.ravel(z_int)
        return x_int_1D, y_int_1D, z_int
    elif z_int is not None:
        z_int_1D = np.ravel(z_int)
        return z_int_1D
    elif x_int is not None and y_int is not None:
        x_int_1D = np.ravel(np.repeat([x_int], np.size(y_int), axis=0))
        y_int_1D = np.ravel(np.repeat([y_int], np.size(x_int), axis=1))
        return x_int_1D, y_int_1D
    else:
        return None
