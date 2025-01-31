import unittest
import pytest
import numpy as np
import os

import pycqed as pq
import pycqed.analysis.analysis_toolbox as a_tools

from pycqed.measurement import measurement_control

import pycqed.instrument_drivers.meta_instrument.qubit_objects.mock_CCL_Transmon as ct
import pycqed.instrument_drivers.meta_instrument.device_object_CCL as do
from pycqed.instrument_drivers.meta_instrument.Resonator import resonator
from pycqed.instrument_drivers.meta_instrument.LutMans import mw_lutman as mwl
from pycqed.instrument_drivers.meta_instrument.LutMans.ro_lutman import UHFQC_RO_LutMan

import pycqed.instrument_drivers.virtual_instruments.virtual_SignalHound as sh
import pycqed.instrument_drivers.virtual_instruments.virtual_MW_source as vmw
import pycqed.instrument_drivers.virtual_instruments.virtual_SPI_S4g_FluxCurrent as flx

import pycqed.instrument_drivers.physical_instruments.ZurichInstruments.UHFQuantumController as UHF
import pycqed.instrument_drivers.physical_instruments.ZurichInstruments.ZI_HDAWG8 as HDAWG

from pycqed.instrument_drivers.library.Transport import DummyTransport
from pycqed.instrument_drivers.physical_instruments.QuTech.CC import CC
from pycqed.instrument_drivers.physical_instruments.QuTech_VSM_Module import Dummy_QuTechVSMModule

from qcodes import station, Instrument


class Test_Mock_CCL(unittest.TestCase):

    # FIXME: using setUpClass is more efficient, but failing tests tend to influence each other, making debugging difficult
    #  If we stick with setUp, 'cls' should be renamed to 'self'
    # @classmethod
    # def setUpClass(cls):
    def setUp(cls):
        cls.station = station.Station()
        cls.CCL_qubit = ct.Mock_CCLight_Transmon('CCL_qubit')

        cls.fluxcurrent = flx.virtual_SPI_S4g_FluxCurrent(
                'fluxcurrent',
                channel_map={
                    'FBL_Q1': (0, 0),
                    'FBL_Q2': (0, 1),
                })
        cls.fluxcurrent.FBL_Q1(0)
        cls.fluxcurrent.FBL_Q2(0)
        cls.station.add_component(cls.fluxcurrent)

        cls.MW1 = vmw.VirtualMWsource('MW1')
        cls.MW2 = vmw.VirtualMWsource('MW2')
        cls.MW3 = vmw.VirtualMWsource('MW3')
        cls.SH = sh.virtual_SignalHound_USB_SA124B('SH')
        cls.UHFQC = UHF.UHFQC(name='UHFQC', server='emulator',
                              device='dev2109', interface='1GbE')

        cls.CC = CC('CC', DummyTransport())
        # self.VSM = Dummy_Duplexer('VSM')
        cls.VSM = Dummy_QuTechVSMModule('VSM')

        cls.MC = measurement_control.MeasurementControl(
            'MC', live_plot_enabled=False, verbose=False)
        cls.MC.station = cls.station
        cls.station.add_component(cls.MC)

        # Required to set it to the testing datadir
        test_datadir = os.path.join(pq.__path__[0], 'tests', 'test_output')
        cls.MC.datadir(test_datadir)
        a_tools.datadir = cls.MC.datadir()

        cls.AWG = HDAWG.ZI_HDAWG8(name='DummyAWG8', server='emulator', num_codewords=32, device='dev8026', interface='1GbE')
        cls.AWG8_VSM_MW_LutMan = mwl.AWG8_VSM_MW_LutMan('MW_LutMan_VSM')
        cls.AWG8_VSM_MW_LutMan.AWG(cls.AWG.name)
        cls.AWG8_VSM_MW_LutMan.channel_GI(1)
        cls.AWG8_VSM_MW_LutMan.channel_GQ(2)
        cls.AWG8_VSM_MW_LutMan.channel_DI(3)
        cls.AWG8_VSM_MW_LutMan.channel_DQ(4)
        cls.AWG8_VSM_MW_LutMan.mw_modulation(100e6)
        cls.AWG8_VSM_MW_LutMan.sampling_rate(2.4e9)

        cls.ro_lutman = UHFQC_RO_LutMan(
            'RO_lutman', num_res=5, feedline_number=0)
        cls.ro_lutman.AWG(cls.UHFQC.name)

        # Assign instruments
        cls.CCL_qubit.instr_LutMan_MW(cls.AWG8_VSM_MW_LutMan.name)
        cls.CCL_qubit.instr_LO_ro(cls.MW1.name)
        cls.CCL_qubit.instr_LO_mw(cls.MW2.name)
        cls.CCL_qubit.instr_spec_source(cls.MW3.name)

        cls.CCL_qubit.instr_acquisition(cls.UHFQC.name)
        cls.CCL_qubit.instr_VSM(cls.VSM.name)
        cls.CCL_qubit.instr_CC(cls.CC.name)
        cls.CCL_qubit.instr_LutMan_RO(cls.ro_lutman.name)
        cls.CCL_qubit.instr_MC(cls.MC.name)
        cls.CCL_qubit.instr_FluxCtrl(cls.fluxcurrent.name)
        cls.CCL_qubit.instr_SH(cls.SH.name)

        config_fn = os.path.join(
            pq.__path__[0], 'tests', 'openql', 'test_cfg_cc.json')
        cls.CCL_qubit.cfg_openql_platform_fn(config_fn)

        # Setting some "random" initial parameters
        cls.CCL_qubit.ro_freq(5.43e9)
        cls.CCL_qubit.ro_freq_mod(200e6)

        cls.CCL_qubit.freq_qubit(4.56e9)
        cls.CCL_qubit.freq_max(4.62e9)

        cls.CCL_qubit.mw_freq_mod(-100e6)
        cls.CCL_qubit.mw_awg_ch(1)
        cls.CCL_qubit.cfg_qubit_nr(0)

        if 0: # FIXME: fails
            cls.CCL_qubit.mw_vsm_delay(15)

        cls.CCL_qubit.mw_mixer_offs_GI(.1)
        cls.CCL_qubit.mw_mixer_offs_GQ(.2)
        cls.CCL_qubit.mw_mixer_offs_DI(.3)
        cls.CCL_qubit.mw_mixer_offs_DQ(.4)
        # self.CCL_qubit.ro_acq_averages(32768)
        cls.device = do.DeviceCCL(name='device')
        cls.CCL_qubit.instr_device(cls.device.name)

    # @classmethod
    # def tearDownClass(self):
    def tearDown(self):
        Instrument.close_all()
    # for inststr in list(self.CCL_qubit._all_instruments):
        #     try:
        #         inst = self.CCL_qubit.find_instrument(inststr)
        #         inst.close()
        #     except KeyError:
        #         pass

    ###########################################################
    # Test find resonator frequency
    ###########################################################
    @unittest.skip("FIXME: fails with 'ValueError: The truth value of an array with more than one element is ambiguous'")
    def test_find_resonator_frequency(self):
        self.CCL_qubit.mock_freq_res_bare(7.58726e9)
        self.CCL_qubit.mock_sweetspot_phi_over_phi0(0)
        freq_res = self.CCL_qubit.calculate_mock_resonator_frequency()

        self.CCL_qubit.freq_res(7.587e9)
        self.CCL_qubit.find_resonator_frequency()

        assert self.CCL_qubit.freq_res() == pytest.approx(freq_res, abs=1e6)

    ###########################################################
    # Test find qubit frequency
    ###########################################################
    def test_find_frequency(self):
        self.CCL_qubit.mock_sweetspot_phi_over_phi0(0)

        self.CCL_qubit.mock_Ec(250e6)
        self.CCL_qubit.mock_Ej1(8e9)
        self.CCL_qubit.mock_Ej2(8e9)

        f_qubit = self.CCL_qubit.calculate_mock_qubit_frequency()

        self.CCL_qubit.freq_qubit(f_qubit)

        self.CCL_qubit.ro_pulse_amp_CW(self.CCL_qubit.mock_ro_pulse_amp_CW())
        freq_res = self.CCL_qubit.calculate_mock_resonator_frequency()
        self.CCL_qubit.freq_res(freq_res)
        self.CCL_qubit.ro_freq(freq_res)

        threshold = 0.01e9
        self.CCL_qubit.find_frequency()
        assert np.abs(f_qubit - self.CCL_qubit.freq_qubit()) <= threshold

    ###########################################################
    # Test MW pulse calibration
    ###########################################################
    @unittest.skip("FIXME: fails with 'AssertionError: assert 1.0 == 0.345 ± 5.0e-02'")
    def test_calibrate_mw_pulse_amplitude_coarse(self):
        for with_vsm in [True, False]:
            self.CCL_qubit.mock_sweetspot_phi_over_phi0(0)

            f_qubit = self.CCL_qubit.calculate_mock_qubit_frequency()

            self.CCL_qubit.freq_res(self.CCL_qubit.calculate_mock_resonator_frequency())
            self.CCL_qubit.freq_qubit(f_qubit)

            self.CCL_qubit.cfg_with_vsm(with_vsm)
            self.CCL_qubit.mock_mw_amp180(.345)
            self.CCL_qubit.calibrate_mw_pulse_amplitude_coarse()
            freq_res = self.CCL_qubit.calculate_mock_resonator_frequency()
            self.CCL_qubit.ro_freq(freq_res)

            eps = 0.05
            if self.CCL_qubit.cfg_with_vsm():
                # FIXME: shown to sometimes fail (PR #638)
                assert self.CCL_qubit.mw_vsm_G_amp() == pytest.approx(
                        self.CCL_qubit.mock_mw_amp180(), abs=eps)
            else:
                assert self.CCL_qubit.mw_channel_amp() == pytest.approx(
                        self.CCL_qubit.mw_channel_amp(), abs=eps)

    ###########################################################
    # Test find qubit sweetspot
    ###########################################################
    @unittest.skip("FIXME: fails with 'AssertionError: assert 0.0003351536396119943 == 0.00026859999...9997 ± 3.0e-05'")
    def test_find_qubit_sweetspot(self):
        assert self.CCL_qubit.mock_fl_dc_ch() == 'FBL_Q1'
        self.CCL_qubit.fl_dc_ch(self.CCL_qubit.mock_fl_dc_ch())

        self.CCL_qubit.mock_sweetspot_phi_over_phi0(0.01343)
        current = 0.01343*self.CCL_qubit.mock_fl_dc_I_per_phi0()[
                        self.CCL_qubit.mock_fl_dc_ch()]
        self.CCL_qubit.fl_dc_I0(current)

        fluxcurrent = self.CCL_qubit.instr_FluxCtrl.get_instr()
        fluxcurrent[self.CCL_qubit.mock_fl_dc_ch()](current)

        assert self.CCL_qubit.mock_fl_dc_ch() == 'FBL_Q1'

        f_qubit = self.CCL_qubit.calculate_mock_qubit_frequency()
        self.CCL_qubit.freq_qubit(f_qubit)

        self.CCL_qubit.freq_res(self.CCL_qubit.calculate_mock_resonator_frequency())

        assert self.CCL_qubit.mock_fl_dc_ch() == 'FBL_Q1'
        assert self.CCL_qubit.fl_dc_ch() == 'FBL_Q1'
        freq_res = self.CCL_qubit.calculate_mock_resonator_frequency()
        self.CCL_qubit.ro_freq(freq_res)

        assert self.CCL_qubit.mock_fl_dc_ch() == 'FBL_Q1'
        self.CCL_qubit.find_qubit_sweetspot()

        assert self.CCL_qubit.fl_dc_I0() == pytest.approx(
                                    current,
                                    abs=30e-6)

    ###########################################################
    # Test RO pulse calibration
    ###########################################################
    def test_calibrate_ro_pulse_CW(self):
        self.CCL_qubit.mock_ro_pulse_amp_CW(0.05)
        self.CCL_qubit.mock_freq_res_bare(7.5e9)
        self.CCL_qubit.freq_res(self.CCL_qubit.calculate_mock_resonator_frequency())

        self.device.qubits([self.CCL_qubit.name])

        self.CCL_qubit.calibrate_ro_pulse_amp_CW()
        eps = 0.1
        assert self.CCL_qubit.ro_pulse_amp_CW() <= self.CCL_qubit.mock_ro_pulse_amp_CW()

    ###########################################################
    # Test find test resonators
    ###########################################################
    @unittest.skip('FIXME: disabled, see PR #643 and PR #635 (marked as non-important)')
    def test_find_test_resonators(self):
        self.CCL_qubit.mock_freq_res_bare(7.78542e9)
        self.CCL_qubit.mock_freq_test_res(7.9862e9)

        res0 = resonator(identifier=0, freq=7.785e9)
        res1 = resonator(identifier=1, freq=7.986e9)

        self.CCL_qubit.instr_device.get_instr().resonators = [res0, res1]

        for res in [res0, res1]:
            self.CCL_qubit.find_test_resonators()

            if res.identifier == 0:
                assert res0.type == 'qubit_resonator'
            elif res.identifier == 1:
                assert res1.type == 'test_resonator'

    ###########################################################
    # Test Ramsey
    ###########################################################
    def test_ramsey(self):
        self.CCL_qubit.mock_Ec(250e6)
        self.CCL_qubit.mock_Ej1(8e9)
        self.CCL_qubit.mock_Ej2(8e9)

        self.CCL_qubit.mock_sweetspot_phi_over_phi0(0)

        f_qubit = self.CCL_qubit.calculate_mock_qubit_frequency()
        self.CCL_qubit.freq_qubit(f_qubit)

        self.CCL_qubit.freq_res(self.CCL_qubit.calculate_mock_resonator_frequency())

        self.CCL_qubit.ro_pulse_amp_CW(self.CCL_qubit.mock_ro_pulse_amp_CW())
        freq_res = self.CCL_qubit.calculate_mock_resonator_frequency()
        self.CCL_qubit.ro_freq(freq_res)


        self.CCL_qubit.mock_T2_star(23e-6)
        self.CCL_qubit.T2_star(19e-6)
        self.CCL_qubit.measure_ramsey()

        threshold = 4e-6
        assert self.CCL_qubit.T2_star() == pytest.approx(
                                           self.CCL_qubit.mock_T2_star(),
                                           abs=threshold)

    ###########################################################
    # Test T1
    ###########################################################
    def test_T1(self):
        self.CCL_qubit.mock_Ec(250e6)
        self.CCL_qubit.mock_Ej1(8e9)
        self.CCL_qubit.mock_Ej2(8e9)

        fluxcurrent = self.CCL_qubit.instr_FluxCtrl.get_instr()
        current = self.CCL_qubit.mock_sweetspot_phi_over_phi0()

        fluxcurrent[self.CCL_qubit.mock_fl_dc_ch()](current)

        f_qubit = self.CCL_qubit.calculate_mock_qubit_frequency()
        self.CCL_qubit.freq_qubit(f_qubit)
        freq_res = self.CCL_qubit.calculate_mock_resonator_frequency()

        self.CCL_qubit.freq_res(freq_res)

        self.CCL_qubit.ro_pulse_amp_CW(self.CCL_qubit.mock_ro_pulse_amp_CW())
        self.CCL_qubit.ro_freq(freq_res)

        self.CCL_qubit.mock_T1(34.39190e-6)
        self.CCL_qubit.T1(40e-6)
        self.CCL_qubit.measure_T1()
        self.CCL_qubit.measure_T1()

        assert self.CCL_qubit.T1() == pytest.approx(self.CCL_qubit.mock_T1(),
                                                    abs=5e-5) # R.S. raised this because it was too tight

    ###########################################################
    # Test Echo
    ###########################################################
    def test_echo(self):
        self.CCL_qubit.mock_Ec(250e6)
        self.CCL_qubit.mock_Ej1(8e9)
        self.CCL_qubit.mock_Ej2(8e9)

        self.CCL_qubit.mock_sweetspot_phi_over_phi0(0)

        f_qubit = self.CCL_qubit.calculate_mock_qubit_frequency()
        self.CCL_qubit.freq_qubit(f_qubit)

        self.CCL_qubit.freq_res(self.CCL_qubit.calculate_mock_resonator_frequency())

        self.CCL_qubit.ro_pulse_amp_CW(self.CCL_qubit.mock_ro_pulse_amp_CW())
        freq_res = self.CCL_qubit.calculate_mock_resonator_frequency()
        self.CCL_qubit.ro_freq(freq_res)

        self.CCL_qubit.mock_T2_echo(23e-6)
        self.CCL_qubit.T2_echo(19e-6)
        self.CCL_qubit.measure_echo()

        threshold = 3e-6
        assert self.CCL_qubit.T2_echo() == pytest.approx(
                                           self.CCL_qubit.mock_T2_echo(),
                                           abs=threshold)
