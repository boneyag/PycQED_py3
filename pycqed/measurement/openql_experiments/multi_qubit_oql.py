from typing import List
import numpy as np

from pycqed.measurement.openql_experiments.openql_helpers import OqlProgram
from pycqed.utilities.general import int2base
from pycqed.instrument_drivers.meta_instrument.LutMans.flux_lutman import _def_lm as _def_lm_flux


def single_flux_pulse_seq(qubit_indices: tuple, platf_cfg: str):
    p = OqlProgram("single_flux_pulse_seq", platf_cfg)

    k = p.create_kernel("main")
    for idx in qubit_indices:
        k.prepz(idx)  # to ensure enough separation in timing
        k.prepz(idx)  # to ensure enough separation in timing
        k.prepz(idx)  # to ensure enough separation in timing

    k.barrier([])
    k.gate('fl_cw_02', [qubit_indices[0], qubit_indices[1]])
    p.add_kernel(k)

    p.compile()
    return p


# FIXME: not really used
def flux_staircase_seq(platf_cfg: str) -> OqlProgram:
    p = OqlProgram("flux_staircase_seq", platf_cfg)

    k = p.create_kernel("main")
    for i in range(1):
        k.prepz(i)  # to ensure enough separation in timing
    for i in range(1):
        k.gate('CW_00', [i])
    k.gate('CW_00', [6])
    for cw in range(8):
        k.gate('fl_cw_{:02d}'.format(cw), [2, 0])
        k.gate('fl_cw_{:02d}'.format(cw), [3, 1])
        k.gate("wait", [0, 1, 2, 3], 200)  # because scheduling is wrong.
    p.add_kernel(k)

    p.compile()
    return p


def multi_qubit_off_on(
        qubits: list,
        initialize: bool,
        second_excited_state: bool,
        platf_cfg: str,
        nr_flux_dance: int = None,
        wait_time: float = None
) -> OqlProgram:
    """
    Performs an 'off_on' sequence on the qubits specified.
        off: (RO) - prepz -      -     - RO
        on:  (RO) - prepz - x180 -     - RO
        2nd  (RO) - prepz - X180 - X12 - RO  (if second_excited_state == True)

    Will cycle through all combinations of off and on. Last qubit in the list
    is considered the Least Significant Qubit (LSQ).

    Args:
        qubits (list) : list of integers denoting the qubits to use
        initialize (bool): if True does an extra initial measurement to
            allow post selecting data.
        second_excited_state (bool): if True includes the 2-state in the
            combinations.
        platf_cfg (str) : filepath of OpenQL platform config file
    """

    if second_excited_state:
        base = 3
    else:
        base = 2

    combinations = [int2base(i, base=base, fixed_length=len(qubits)) for
                    i in range(base ** len(qubits))]

    p = OqlProgram("multi_qubit_off_on", platf_cfg)

    for i, comb in enumerate(combinations):
        k = p.create_kernel('Prep_{}'.format(comb))

        # 1. Prepare qubits in 0
        for q in qubits:
            k.prepz(q)
        k.barrier([])

        # 2. post-selection extra init readout
        if initialize:
            for q in qubits:
                k.measure(q)
            k.barrier(qubits)

        if nr_flux_dance:
            for i in range(int(nr_flux_dance)):
                for step in [1, 2, 3, 4]:
                    # if refocusing:
                    #     k.gate(f'flux-dance-{step}-refocus', [0])
                    # else:
                    k.gate(f'flux-dance-{step}', [0])
                k.barrier([])  # alignment
            k.gate("wait", [], wait_time)

            # 3. prepare desired state
        for state, target_qubit in zip(comb, qubits):  # N.B. last is LSQ
            if state == '0':
                k.gate('i', [target_qubit])
            elif state == '1':
                k.gate('rx180', [target_qubit])
            elif state == '2':
                k.gate('rx180', [target_qubit])
                k.gate('rx12', [target_qubit])
        # 4. measurement of all qubits
        k.barrier(qubits)
        # Used to ensure timing is aligned
        for q in qubits:
            k.measure(q)
        k.barrier(qubits)
        p.add_kernel(k)

    p.compile()

    return p


def single_qubit_off_on(
        qubits: list,
        qtarget,
        initialize: bool,
        platf_cfg: str
) -> OqlProgram:
    n_qubits = len(qubits)
    comb_0 = '0' * n_qubits
    comb_1 = comb_0[:qubits.index(qtarget)] + '1' + comb_0[qubits.index(qtarget) + 1:]

    combinations = [comb_0, comb_1]

    p = OqlProgram("single_qubit_off_on", platf_cfg)

    for i, comb in enumerate(combinations):
        k = p.create_kernel('Prep_{}'.format(comb))

        # 1. Prepare qubits in 0
        for q in qubits:
            k.prepz(q)

        # 2. post-selection extra init readout
        if initialize:
            for q in qubits:
                k.measure(q)
            k.barrier(qubits)

        # 3. prepare desired state
        for state, target_qubit in zip(comb, qubits):  # N.B. last is LSQ
            if state == '0':
                pass
            elif state == '1':
                k.gate('rx180', [target_qubit])
            elif state == '2':
                k.gate('rx180', [target_qubit])
                k.gate('rx12', [target_qubit])
        # 4. measurement of all qubits
        k.barrier(qubits)
        # Used to ensure timing is aligned
        for q in qubits:
            k.measure(q)
        k.barrier(qubits)
        p.add_kernel(k)

    p.compile()

    return p


def targeted_off_on(
        qubits: list,
        q_target: int,
        pulse_comb: str,
        platf_cfg: str
) -> OqlProgram:
    """
    Performs an 'off_on' sequence on the qubits specified.
        off: prepz -      - RO
        on:  prepz - x180 - RO

    Will cycle through all combinations of computational states of every
    qubit in <qubits> except the target qubit. The target qubit will be
    initialized according to <pulse_comb>. 'Off' initializes the qubit in
    the ground state and 'On' initializes the qubit in the excited state.

    Args:
        qubits (list) : list of integers denoting the qubits to use
        q_target (str) : targeted qubit.
        pulse_comb (str) : prepared state of target qubit.
        platf_cfg (str) : filepath of OpenQL platform config file
    """

    nr_qubits = len(qubits)
    idx = qubits.index(q_target)

    combinations = ['{:0{}b}'.format(i, nr_qubits - 1) for i in range(2 ** (nr_qubits - 1))]
    for i, comb in enumerate(combinations):
        comb = list(comb)  #
        if 'on' in pulse_comb.lower():
            comb.insert(idx, '1')
        elif 'off' in pulse_comb.lower():
            comb.insert(idx, '0')
        else:
            raise ValueError()
        combinations[i] = ''.join(comb)

    p = OqlProgram("Targeted_off_on", platf_cfg)

    for i, comb in enumerate(combinations):
        k = p.create_kernel('Prep_{}'.format(comb))

        # 1. Prepare qubits in 0
        for q in qubits:
            k.prepz(q)

        # 2. prepare desired state
        for state, target_qubit in zip(comb, qubits):  # N.B. last is LSQ
            if state == '0':
                pass
            elif state == '1':
                k.gate('rx180', [target_qubit])

        # 3. measurement of all qubits
        k.barrier(qubits)
        # Used to ensure timing is aligned
        for q in qubits:
            k.measure(q)
        k.barrier(qubits)
        p.add_kernel(k)

    p.compile()

    return p

def Msmt_induced_dephasing_ramsey(
    q_rams: list,
    q_meas: int,
    meas_time: int,
    platf_cfg: str,
    echo_times: list = None,
    exception_qubits: list = None
) -> OqlProgram:
    """
    q_target is ramseyed
    q_spec is measured

    """
    p = OqlProgram("Ramsey_msmt_induced_dephasing", platf_cfg)

    angles = np.arange(0,360,20)
    for i, angle in enumerate(angles):
        for meas in [False, True]:
            for state in ['0', '1']:
                cw_idx = angle//20 + 9
                k = p.create_kernel(f"Ramsey_meas_{meas}_{angle}_{state}")

                for q in q_rams:
                    k.prepz(q)
                k.prepz(q_meas)
                k.barrier([])

                if state == '1':
                    k.gate('rx180',[q_meas])
                for q in q_rams:
                    k.gate('rx90', [q])
                k.barrier([])

                if meas == True:
                    k.measure(q_meas)
                else:
                    k.gate('wait', [q_meas], meas_time)
                if echo_times != None:
                    for q, t in zip(q_rams, echo_times):
                        k.gate('cw_30', [q])
                        k.gate('wait', [q], t)
                k.barrier([]) 
                
                for q in q_rams:
                    k.gate('cw_{:02}'.format(cw_idx), [q])
                    k.gate("wait", [q], 600) # To prevent UHF from missing shots
                    k.measure(q)
                k.barrier([])
                if meas == True and exception_qubits != None:
                    for q in exception_qubits:
                        k.measure(q)
                p.add_kernel(k)

    # adding the calibration points
    n = len(q_rams)
    p.add_multi_q_cal_points(
        qubits=q_rams,
        combinations=['0' * n, '1' * n],
        reps_per_cal_pnt=2
    )

    p.compile()
    return p



def two_qubit_off_on(q0: int, q1: int, platf_cfg: str):
    '''
    off_on sequence on two qubits.

    # FIXME: input arg should be "qubits" as a list

    Args:
        q0, q1      (int) : target qubits for the sequence
        platf_cfg: str
    '''
    p = OqlProgram('two_qubit_off_on', platf_cfg)

    p.add_two_q_cal_points(q0=q0, q1=q1)

    p.compile()
    return p


def two_qubit_tomo_cardinal(q0: int, q1: int, cardinal: int, platf_cfg: str) -> OqlProgram:
    '''
    Cardinal tomography for two qubits.
    Args:
        cardinal        (int) : index of prep gate
        q0, q1          (int) : target qubits for the sequence
    '''
    tomo_pulses = ['i', 'rx180', 'ry90', 'rym90', 'rx90', 'rxm90']
    tomo_list_q0 = tomo_pulses
    tomo_list_q1 = tomo_pulses

    prep_index_q0 = int(cardinal % len(tomo_list_q0))
    prep_index_q1 = int(((cardinal - prep_index_q0) / len(tomo_list_q0) %
                         len(tomo_list_q1)))

    prep_pulse_q0 = tomo_list_q0[prep_index_q0]
    prep_pulse_q1 = tomo_list_q1[prep_index_q1]

    p = OqlProgram('two_qubit_tomo_cardinal', platf_cfg)

    # Tomography pulses
    i = 0
    for p_q1 in tomo_list_q1:
        for p_q0 in tomo_list_q0:
            i += 1
            kernel_name = '{}_{}_{}'.format(i, p_q0, p_q1)
            k = p.create_kernel(kernel_name)
            k.prepz(q0)
            k.prepz(q1)
            k.gate(prep_pulse_q0, [q0])
            k.gate(prep_pulse_q1, [q1])
            k.gate(p_q0, [q0])
            k.gate(p_q1, [q1])
            k.measure(q0)
            k.measure(q1)
            p.add_kernel(k)
    # every calibration point is repeated 7 times. This is copied from the
    # script for Tektronix driven qubits. I do not know if this repetition
    # is important or even necessary here.
    p.add_two_q_cal_points(q0=q1, q1=q0, reps_per_cal_pt=7)

    p.compile()
    return p


def two_qubit_AllXY(
        q0: int,
        q1: int,
        platf_cfg: str,
        sequence_type='sequential',
        replace_q1_pulses_with: str = None,
        repetitions: int = 1
) -> OqlProgram:
    """
    AllXY sequence on two qubits.
    Has the option of replacing pulses on q1 with pi pulses

    Args:
        q0, q1         (str) : target qubits for the sequence
        sequence_type  (str) : Describes the timing/order of the pulses.
            options are: sequential | interleaved | simultaneous | sandwiched
                       q0|q0|q1|q1   q0|q1|q0|q1     q01|q01       q1|q0|q0|q1
            describes the order of the AllXY pulses
        replace_q1_pulses_with (bool) : if True replaces all pulses on q1 with
            X180 pulses.

        double_points (bool) : if True measures each point in the AllXY twice
    """
    p = OqlProgram('two_qubit_AllXY', platf_cfg)

    pulse_combinations = [['i', 'i'], ['rx180', 'rx180'], ['ry180', 'ry180'],
                          ['rx180', 'ry180'], ['ry180', 'rx180'],
                          ['rx90', 'i'], ['ry90', 'i'], ['rx90', 'ry90'],
                          ['ry90', 'rx90'], ['rx90', 'ry180'],
                          ['ry90', 'rx180'],
                          ['rx180', 'ry90'], ['ry180', 'rx90'],
                          ['rx90', 'rx180'],
                          ['rx180', 'rx90'], ['ry90', 'ry180'],
                          ['ry180', 'ry90'],
                          ['rx180', 'i'], ['ry180', 'i'], ['rx90', 'rx90'],
                          ['ry90', 'ry90']]

    pulse_combinations_q0 = np.repeat(pulse_combinations, repetitions, axis=0)

    if replace_q1_pulses_with is not None:
        # pulse_combinations_q1 = [[replace_q1_pulses_with]*2 for val in pulse_combinations]
        pulse_combinations_q1 = np.repeat(
            [[replace_q1_pulses_with] * 2], len(pulse_combinations_q0), axis=0)
    else:
        pulse_combinations_q1 = np.tile(pulse_combinations, [repetitions, 1])
    i = 0
    for pulse_comb_q0, pulse_comb_q1 in zip(pulse_combinations_q0,
                                            pulse_combinations_q1):
        i += 1
        k = p.create_kernel('AllXY_{}'.format(i))
        k.prepz(q0)
        k.prepz(q1)
        # N.B. The identity gates are there to ensure proper timing
        if sequence_type == 'interleaved':
            k.gate(pulse_comb_q0[0], [q0])
            k.gate('i', [q1])

            k.gate('i', [q0])
            k.gate(pulse_comb_q1[0], [q1])

            k.gate(pulse_comb_q0[1], [q0])
            k.gate('i', [q1])

            k.gate('i', [q0])
            k.gate(pulse_comb_q1[1], [q1])

        elif sequence_type == 'sandwiched':
            k.gate('i', [q0])
            k.gate(pulse_comb_q1[0], [q1])

            k.gate(pulse_comb_q0[0], [q0])
            k.gate('i', [q1])
            k.gate(pulse_comb_q0[1], [q0])
            k.gate('i', [q1])

            k.gate('i', [q0])
            k.gate(pulse_comb_q1[1], [q1])

        elif sequence_type == 'sequential':
            k.gate(pulse_comb_q0[0], [q0])
            k.gate('i', [q1])
            k.gate(pulse_comb_q0[1], [q0])
            k.gate('i', [q1])
            k.gate('i', [q0])
            k.gate(pulse_comb_q1[0], [q1])
            k.gate('i', [q0])
            k.gate(pulse_comb_q1[1], [q1])

        elif sequence_type == 'simultaneous':
            k.gate(pulse_comb_q0[0], [q0])
            k.gate(pulse_comb_q1[0], [q1])
            k.gate(pulse_comb_q0[1], [q0])
            k.gate(pulse_comb_q1[1], [q1])
        else:
            raise ValueError("sequence_type {} ".format(sequence_type) +
                             "['interleaved', 'simultaneous', " +
                             "'sequential', 'sandwiched']")
        k.measure(q0)
        k.measure(q1)
        p.add_kernel(k)

    p.compile()
    return p


def residual_coupling_sequence(
        times,
        q0: int,
        q_spectator_idx: list,
        spectator_state: str,
        platf_cfg: str
) -> OqlProgram:
    """
    Sequence to measure the residual (ZZ) interaction between two qubits.
    Procedure is described in M18TR.

        (q0) --X90----(tau)---Y180-(tau)-Y90---RO
        (qs) --[X180]-(tau)-[X180]-(tau)-------RO

    Input pars:
        times:           the list of waiting times in s for each Echo element
        q0               Phase measurement is performed on q0
        q_spectator_idx  Excitation is put in and removed on these qubits
                         as indicated
        spectator_state  Indicates on which qubit to put excitations.
        platf_cfg:       filename of the platform config file
    Returns:
        p:              OpenQL Program object containing

    """

    p = OqlProgram("residual_coupling_sequence", platf_cfg)
    all_qubits = [q0] + q_spectator_idx
    n_qubits = len(all_qubits)

    gate_spec = [s.replace('0', 'i').replace('1', 'rx180') for s in spectator_state]

    for i, time in enumerate(times[:-4]):

        k = p.create_kernel("residual_coupling_seq_{}".format(i))
        k.prepz(q0)
        for q_s in q_spectator_idx:
            k.prepz(q_s)
        wait_nanoseconds = int(round(time / 1e-9))
        k.gate('rx90', [q0])

        # wait
        k.gate("wait", all_qubits, wait_nanoseconds)

        # Echo pulse on ramsey qubit, apply selected gate again to cancel effect
        k.gate('rx180', [q0])
        for i_s, q_s in enumerate(q_spectator_idx):
            k.gate(gate_spec[i_s], [q_s])

        # wait
        k.gate("wait", all_qubits, wait_nanoseconds)

        # Transform ramsey qubit state to preferred basis
        # angle = (i*40) % 360
        # cw_idx = angle//20 + 9
        # k.gate('cw_{:02}'.format(cw_idx), [q0])
        k.gate('ry90', [q0])
        # k.gate('rxm90', [q0])
        for i_s, q_s in enumerate(q_spectator_idx):
            k.gate(gate_spec[i_s], [q_s])
        k.gate('wait', [], 0)

        # Measure qubits
        k.measure(q0)
        for q_s in q_spectator_idx:
            k.measure(q_s)
        k.barrier(all_qubits)
        p.add_kernel(k)

    # adding the calibration points
    p.add_multi_q_cal_points(
        qubits=all_qubits,
        combinations=['0' * n_qubits, '1' * n_qubits])

    p.compile()
    return p


def FluxTimingCalibration(
        qubit_idxs: list,
        platf_cfg: str,
        flux_cw: str = 'fl_cw_02',  # FIXME: unused
        cal_points: bool = True
) -> OqlProgram:
    """
    A Ramsey sequence with varying waiting times `times` around a flux pulse.
    """
    p = OqlProgram('FluxTimingCalibration', platf_cfg)

    # don't use last 4 points if calibration points are used
    k = p.create_kernel('pi_flux_pi')

    k.prepz(qubit_idxs[0])
    for q_idx in qubit_idxs:
        k.gate('rx90', [q_idx])
    k.barrier([])  # alignment workaround
    for q_idx in qubit_idxs:
        k.gate('sf_square', [q_idx])
    k.barrier([])  # alignment workaround
    for q_idx in qubit_idxs:
        k.gate('rx90', [q_idx])
    k.barrier([])  # alignment workaround
    for q_idx in qubit_idxs:
        k.measure(q_idx)
    p.add_kernel(k)

    if cal_points:
        p.add_single_qubit_cal_points(qubit_idx=qubit_idx)  # FIXME: unresolved, use multi iso single?
    p.compile()
    return p


def Cryoscope(
        qubit_idxs: list,
        flux_cw: str = 'fl_cw_06',  # FIXME: effectively unused
        twoq_pair=[2, 0],
        platf_cfg: str = '',
        cc: str = 'CC',
        double_projections: bool = True
) -> OqlProgram:
    """
    Single qubit Ramsey sequence.
    Writes output files to the directory specified in openql.
    Output directory is set as an attribute to the program for convenience.

    Input pars:
        times:          the list of waiting times for each Ramsey element
       q0idx,q1idx      int specifying the target qubit (starting at 0)
        platf_cfg:      filename of the platform config file
    Returns:
        p:              OpenQL Program object containing

    """

    p = OqlProgram("Cryoscope", platf_cfg)

    # FIXME: the variables created here are effectively unused
    if cc.upper() == 'CCL':
        flux_target = twoq_pair
    elif cc.upper() == 'QCC' or cc.upper() == 'CC':
        cw_idx = int(flux_cw[-2:])
        flux_cw = 'sf_{}'.format(_def_lm_flux[cw_idx]['name'].lower())
    else:
        raise ValueError('CC type not understood: {}'.format(cc))

    k = p.create_kernel("RamZ_X")
    k.prepz(qubit_idxs[0])
    k.barrier([])  # alignment workaround
    for q_idx in qubit_idxs:
        k.gate('rx90', [q_idx])
    k.barrier([])  # alignment workaround
    for q_idx in qubit_idxs:
        k.gate('sf_square', [q_idx])
    k.barrier([])  # alignment workaround
    for q_idx in qubit_idxs:
        k.gate('rx90', [q_idx])
    k.barrier([])
    for q_idx in qubit_idxs:
        k.measure(q_idx)
    p.add_kernel(k)

    k = p.create_kernel("RamZ_Y")
    k.prepz(qubit_idxs[0])
    k.barrier([])  # alignment workaround
    for q_idx in qubit_idxs:
        k.gate('rx90', [q_idx])
    k.barrier([])  # alignment workaround
    for q_idx in qubit_idxs:
        k.gate('sf_square', [q_idx])
    k.barrier([])  # alignment workaround
    for q_idx in qubit_idxs:
        k.gate('ry90', [q_idx])
    k.barrier([])
    for q_idx in qubit_idxs:
        k.measure(q_idx)
    p.add_kernel(k)

    if double_projections:
        k = p.create_kernel("RamZ_mX")
        k.prepz(qubit_idxs[0])
        k.barrier([])  # alignment workaround
        for q_idx in qubit_idxs:
            k.gate('rx90', [q_idx])
        k.barrier([])  # alignment workaround
        for q_idx in qubit_idxs:
            k.gate('sf_square', [q_idx])
        k.barrier([])  # alignment workaround
        for q_idx in qubit_idxs:
            k.gate('rxm90', [q_idx])
        k.barrier([])
        for q_idx in qubit_idxs:
            k.measure(q_idx)
        p.add_kernel(k)

        k = p.create_kernel("RamZ_mY")
        k.prepz(qubit_idxs[0])
        k.barrier([])  # alignment workaround
        for q_idx in qubit_idxs:
            k.gate('rx90', [q_idx])
        k.barrier([])  # alignment workaround
        for q_idx in qubit_idxs:
            k.gate('sf_square', [q_idx])
        k.barrier([])  # alignment workaround
        for q_idx in qubit_idxs:
            k.gate('rym90', [q_idx])
        k.barrier([])
        for q_idx in qubit_idxs:
            k.measure(q_idx)
        p.add_kernel(k)

    p.compile()
    return p


# FIXME: not really used
def CryoscopeGoogle(qubit_idx: int, buffer_time1, times, platf_cfg: str) -> OqlProgram:
    """
    A Ramsey sequence with varying waiting times `times` around a flux pulse.
    Generates 2xlen(times) measurements (t1-x, t1-y, t2-x, t2-y. etc)
    """
    p = OqlProgram("CryoscopeGoogle", platf_cfg)

    buffer_nanoseconds1 = int(round(buffer_time1 / 1e-9))

    for i_t, t in enumerate(times):
        t_nanoseconds = int(round(t / 1e-9))

        k = p.create_kernel("RamZ_X_{}".format(i_t))
        k.prepz(qubit_idx)
        k.gate('rx90', [qubit_idx])
        k.barrier([])  # alignment workaround
        k.gate("wait", [qubit_idx], buffer_nanoseconds1)
        k.gate('fl_cw_02', [2, 0])
        k.gate("wait", [qubit_idx], t_nanoseconds)
        k.barrier([])  # alignment workaround
        k.gate('rx90', [qubit_idx])
        k.measure(qubit_idx)
        p.add_kernel(k)

        k = p.create_kernel("RamZ_Y_{}".format(i_t))
        k.prepz(qubit_idx)
        k.gate('rx90', [qubit_idx])
        k.barrier([])  # alignment workaround
        k.gate("wait", [qubit_idx], buffer_nanoseconds1)
        k.gate('fl_cw_02', [2, 0])
        k.gate("wait", [qubit_idx], t_nanoseconds)
        k.barrier([])  # alignment workaround
        k.gate('ry90', [qubit_idx])
        k.measure(qubit_idx)
        p.add_kernel(k)

    p.compile()
    return p


def fluxed_ramsey(
        qubit_idx: int,
        wait_time: float,
        flux_cw: str = 'fl_cw_02',
        platf_cfg: str = ''
) -> OqlProgram:
    """
    Single qubit Ramsey sequence.
    Writes output files to the directory specified in openql.
    Output directory is set as an attribute to the program for convenience.

    Input pars:
        maxtime:        longest plux pulse time
        qubit_idx:      int specifying the target qubit (starting at 0)
        platf_cfg:      filename of the platform config file
    Returns:
        p:              OpenQL Program object containing

    """
    p = OqlProgram('OpenQL_Platform', platf_cfg)
    wait_time = wait_time / 1e-9

    k = p.create_kernel("fluxed_ramsey_1")
    k.prepz(qubit_idx)
    k.gate('rx90', qubit_idx)
    k.barrier([])  # alignment workaround
    k.gate(flux_cw, 2, 0)
    k.gate("wait", [qubit_idx], wait_time)
    k.barrier([])  # alignment workaround
    k.gate('rx90', qubit_idx)
    k.measure(qubit_idx)
    p.add_kernel(k)

    k = p.create_kernel("fluxed_ramsey_2")
    k.prepz(qubit_idx)
    k.barrier([])  # alignment workaround
    k.gate('rx90', qubit_idx)
    k.gate(flux_cw, 2, 0)
    k.gate("wait", [qubit_idx], wait_time)
    k.barrier([])  # alignment workaround
    k.gate('ry90', qubit_idx)
    k.measure(qubit_idx)
    p.add_kernel(k)

    # adding the calibration points
    # add_single_qubit_cal_points(p, platf=platf, qubit_idx=qubit_idx)

    p.compile()

    return p


# FIMXE: merge into the real chevron seq


def Chevron_hack(
        qubit_idx: int,
        qubit_idx_spec,
        buffer_time,
        buffer_time2,
        platf_cfg: str
) -> OqlProgram:
    """
    Single qubit Ramsey sequence.
    Writes output files to the directory specified in openql.
    Output directory is set as an attribute to the program for convenience.

    Input pars:
        times:          the list of waiting times for each Ramsey element
        qubit_idx:      int specifying the target qubit (starting at 0)
        platf_cfg:      filename of the platform config file
    Returns:
        p:              OpenQL Program object containing

    """
    p = OqlProgram("Chevron_hack", platf_cfg)

    buffer_nanoseconds = int(round(buffer_time / 1e-9))
    buffer_nanoseconds2 = int(round(buffer_time / 1e-9))

    k = p.create_kernel("Chevron_hack")
    k.prepz(qubit_idx)
    k.gate('rx90', [qubit_idx_spec])
    k.gate('rx180', [qubit_idx])
    k.barrier([])  # alignment workaround
    k.gate("wait", [qubit_idx], buffer_nanoseconds)
    k.gate('fl_cw_02', [2, 0])
    k.gate('wait', [qubit_idx], buffer_nanoseconds2)
    k.barrier([])  # alignment workaround
    k.gate('rx180', [qubit_idx])
    k.measure(qubit_idx)
    k.measure(qubit_idx_spec)
    p.add_kernel(k)

    p.compile()
    return p


def Chevron(
        qubit_idx: int,
        qubit_idx_spec: int,
        qubit_idx_parks: int,  # FIXME: incorrect type
        buffer_time, buffer_time2,
        flux_cw: int,
        platf_cfg: str,
        target_qubit_sequence: str = 'ramsey',
        cc: str = 'CCL',
        recover_q_spec: bool = False
) -> OqlProgram:
    """
    Writes output files to the directory specified in openql.
    Output directory is set as an attribute to the program for convenience.

    Input pars:
        qubit_idx:      int specifying the target qubit (starting at 0)
        qubit_idx_spec: int specifying the spectator qubit
        buffer_time   :
        buffer_time2  :
        measure_parked_qubit (bool): Whether we set a measurement on the parked qubit
        platf_cfg:      filename of the platform config file
        target_qubit_sequence: selects whether to run a ramsey sequence on
            a target qubit ('ramsey'), keep it in gorund state ('ground')
            or excite it iat the beginning of the sequnce ('excited')
        recover_q_spec (bool): applies the first gate of qspec at the end
            as well if `True`
    Returns:
        p:              OpenQL Program object containing


    Circuit:
        q0    -x180-flux-x180-RO-
        qspec --x90-----(x90)-RO- (target_qubit_sequence='ramsey')

        q0    -x180-flux-x180-RO-
        qspec -x180----(x180)-RO- (target_qubit_sequence='excited')

        q0    -x180-flux-x180-RO-
        qspec ----------------RO- (target_qubit_sequence='ground')

    """
    p = OqlProgram("Chevron", platf_cfg)

    buffer_nanoseconds = int(round(buffer_time / 1e-9))
    buffer_nanoseconds2 = int(round(buffer_time2 / 1e-9))
    if flux_cw is None:
        flux_cw = 2
    flux_cw_name = _def_lm_flux[flux_cw]['name'].lower()

    k = p.create_kernel("Chevron")
    k.prepz(qubit_idx)
    k.prepz(qubit_idx_spec)
    if (qubit_idx_parks is not None):
        for q in qubit_idx_parks:
            k.prepz(q)

    spec_gate_dict = {
        "ramsey": "rx90",
        "excited": "rx180",
        "ground": "i"
    }

    spec_gate = spec_gate_dict[target_qubit_sequence]

    k.gate(spec_gate, [qubit_idx_spec])
    k.gate('rx180', [qubit_idx])

    if buffer_nanoseconds > 0:
        k.gate("wait", [qubit_idx], buffer_nanoseconds)

    # For CCLight
    if cc.upper() == 'CCL':
        k.barrier([])  # alignment workaround
        # k.gate('fl_cw_{:02}'.format(flux_cw), [2, 0])
        if qubit_idx_parks is not None:
            for q_park in qubit_idx_parks:
                k.gate('fl_cw_05', [q_park])  # square pulse
        k.barrier([])  # alignment workaround
    elif cc.upper() == 'QCC' or cc.upper() == 'CC':
        k.barrier([])  # alignment workaround
        if qubit_idx_parks is not None:
            for q_park in qubit_idx_parks:
                k.gate('sf_square', [q_park])  # square pulse
        # k.gate('sf_{}'.format(flux_cw_name), [qubit_idx])
        k.gate('sf_square', [qubit_idx])
        k.barrier([])  # alignment workaround
    else:
        raise ValueError('CC type not understood: {}'.format(cc))

    if buffer_nanoseconds2 > 0:
        k.gate('wait', [qubit_idx], buffer_nanoseconds2)

    k.gate('rx180', [qubit_idx])
    k.gate('rx180', [qubit_idx_spec])

    if recover_q_spec:
        k.gate(spec_gate, [qubit_idx_spec])

    k.barrier([])  # alignment workaround
    k.measure(qubit_idx)
    k.measure(qubit_idx_spec)

    p.add_kernel(k)

    p.compile()
    return p


def two_qubit_ramsey(
        times,
        qubit_idx: int,
        qubit_idx_spec: int,
        platf_cfg: str,
        target_qubit_sequence: str = 'excited'
) -> OqlProgram:
    """
    Writes output files to the directory specified in openql.
    Output directory is set as an attribute to the program for convenience.

    Input pars:
        times:          the list of waiting times for each Ramsey element
        qubit_idx:      int specifying the target qubit (starting at 0)
        qubit_idx_spec: int specifying the spectator qubit

        platf_cfg:      filename of the platform config file
        target_qubit_sequence: selects whether to run a ramsey sequence on
            a target qubit ('ramsey'), keep it in gorund state ('ground')
            or excite it iat the beginning of the sequnce ('excited')
    Returns:
        p:              OpenQL Program object containing


    Circuit:
        q0    --x90-wait-x90-RO-
        qspec --x90----------RO- (target_qubit_sequence='ramsey')

        q0    --x90-wait-x90-RO-
        qspec -x180----------RO- (target_qubit_sequence='excited')

        q0    --x90-wait-x90-RO-
        qspec ---------------RO- (target_qubit_sequence='ground')

    """
    p = OqlProgram("two_qubit_ramsey", platf_cfg)

    for i, time in enumerate(times):
        k = p.create_kernel("two_qubit_ramsey_{}".format(i))
        k.prepz(qubit_idx)

        if target_qubit_sequence == 'ramsey':
            k.gate('rx90', [qubit_idx_spec])
        elif target_qubit_sequence == 'excited':
            k.gate('rx180', [qubit_idx_spec])
        elif target_qubit_sequence == 'ground':
            k.gate('i', [qubit_idx_spec])
        else:
            raise ValueError('target_qubit_sequence not recognized.')
        k.gate('rx90', [qubit_idx])

        wait_nanoseconds = int(round(time / 1e-9))
        k.gate("wait", [qubit_idx, qubit_idx_spec], wait_nanoseconds)

        k.gate('i', [qubit_idx_spec])
        k.gate('rx90', [qubit_idx])

        k.measure(qubit_idx)
        k.measure(qubit_idx_spec)
        k.barrier([qubit_idx, qubit_idx_spec])
        p.add_kernel(k)

    # adding the calibration points
    p.add_two_q_cal_points(qubit_idx, qubit_idx_spec, reps_per_cal_pt=2)
    p.compile()
    return p


def two_qubit_tomo_bell(
        bell_state,
        q0,
        q1,
        platf_cfg,
        wait_after_flux: float = None,
        flux_codeword: str = 'cz'
) -> OqlProgram:
    '''
    Two qubit bell state tomography.

    Args:
        bell_state      (int): index of prepared bell state
        q0, q1          (str): names of the target qubits
        wait_after_flux (float): wait time after the flux pulse and
            after-rotation before tomographic rotations
    '''
    tomo_gates = ['i', 'rx180', 'ry90', 'rym90', 'rx90', 'rxm90']

    # Choose a bell state and set the corresponding preparation pulses
    if bell_state == 0:  # |Phi_m>=|00>-|11>
        prep_pulse_q0, prep_pulse_q1 = 'ry90', 'ry90'
    elif bell_state % 10 == 1:  # |Phi_p>=|00>+|11>
        prep_pulse_q0, prep_pulse_q1 = 'rym90', 'ry90'
    elif bell_state % 10 == 2:  # |Psi_m>=|01>-|10>
        prep_pulse_q0, prep_pulse_q1 = 'ry90', 'rym90'
    elif bell_state % 10 == 3:  # |Psi_p>=|01>+|10>
        prep_pulse_q0, prep_pulse_q1 = 'rym90', 'rym90'
    else:
        raise ValueError('Bell state {} is not defined.'.format(bell_state))

    # Recovery pulse is the same for all Bell states
    after_pulse_q1 = 'rym90'

    # # Define compensation pulses
    # # FIXME: needs to be added
    # print('Warning: not using compensation pulses.')

    p = OqlProgram("two_qubit_tomo_bell_{}_{}".format(q1, q0), platf_cfg)
    for p_q1 in tomo_gates:
        for p_q0 in tomo_gates:
            k = p.create_kernel("BellTomo_{}{}_{}{}".format(q1, p_q1, q0, p_q0))
            # next experiment
            k.prepz(q0)  # to ensure enough separation in timing
            k.prepz(q1)  # to ensure enough separation in timing
            # pre-rotations
            k.gate(prep_pulse_q0, [q0])
            k.gate(prep_pulse_q1, [q1])
            # FIXME hardcoded edge because of
            # brainless "directed edge recources" in compiler
            k.barrier([])
            # k.gate('cz', [q0, q1])
            k.gate(flux_codeword, [q0, q1])
            k.barrier([])
            # after-rotations
            k.gate(after_pulse_q1, [q1])
            # possibly wait
            if wait_after_flux is not None:
                k.gate("wait", [q0, q1], round(wait_after_flux * 1e9))
            # tomo pulses
            k.gate(p_q0, [q1])
            k.gate(p_q1, [q0])
            # measure
            k.measure(q0)
            k.measure(q1)
            # sync barrier before tomo
            # k.gate("wait", [q0, q1], 0)
            # k.gate("wait", [2, 0], 0)
            p.add_kernel(k)
    # 7 repetitions is because of assumptions in tomo analysis
    p.add_two_q_cal_points(q0=q0, q1=q1, reps_per_cal_pt=7)
    p.compile()
    return p


def two_qubit_tomo_bell_by_waiting(
        bell_state,
        q0,
        q1,
        platf_cfg,
        wait_time: int = 20
) -> OqlProgram:
    '''
    Two qubit (bell) state tomography. There are no flux pulses applied,
    only waiting time. It is supposed to take advantage of residual ZZ to
    generate entanglement.

    Args:
        bell_state      (int): index of prepared bell state
        q0, q1          (str): names of the target qubits
        wait_time       (int): waiting time in which residual ZZ acts
                                    on qubits
    '''
    tomo_gates = ['i', 'rx180', 'ry90', 'rym90', 'rx90', 'rxm90']

    # Choose a bell state and set the corresponding preparation pulses
    if bell_state == 0:  # |Phi_m>=|00>-|11>
        prep_pulse_q0, prep_pulse_q1 = 'ry90', 'ry90'
    elif bell_state % 10 == 1:  # |Phi_p>=|00>+|11>
        prep_pulse_q0, prep_pulse_q1 = 'rym90', 'ry90'
    elif bell_state % 10 == 2:  # |Psi_m>=|01>-|10>
        prep_pulse_q0, prep_pulse_q1 = 'ry90', 'rym90'
    elif bell_state % 10 == 3:  # |Psi_p>=|01>+|10>
        prep_pulse_q0, prep_pulse_q1 = 'rym90', 'rym90'
    else:
        raise ValueError('Bell state {} is not defined.'.format(bell_state))

    # Recovery pulse is the same for all Bell states
    after_pulse_q1 = 'rym90'

    p = OqlProgram("two_qubit_tomo_bell_by_waiting", platf_cfg)
    for p_q1 in tomo_gates:
        for p_q0 in tomo_gates:
            k = p.create_kernel("BellTomo_{}{}_{}{}".format(
                q1, p_q1, q0, p_q0))
            # next experiment
            k.prepz(q0)  # to ensure enough separation in timing
            k.prepz(q1)  # to ensure enough separation in timing
            # pre-rotations
            k.gate(prep_pulse_q0, [q0])
            k.gate(prep_pulse_q1, [q1])

            if wait_time > 0:
                k.wait([q0, q1], wait_time)

            k.gate(after_pulse_q1, [q1])
            # tomo pulses
            k.gate(p_q1, [q0])
            k.gate(p_q0, [q1])
            # measure
            k.measure(q0)
            k.measure(q1)
            # sync barrier before tomo
            # k.gate("wait", [q0, q1], 0)
            k.barrier([2, 0])
            p.add_kernel(k)
    # 7 repetitions is because of assumptions in tomo analysis
    p.add_two_q_cal_points(q0=q0, q1=q1, reps_per_cal_pt=7)
    p.compile()
    return p


# FIXME: not really used
def two_qubit_DJ(q0, q1, platf_cfg) -> OqlProgram:
    '''
    Two qubit Deutsch-Josza.

    Args:
        q0, q1          (str): names of the target qubits
    '''

    p = OqlProgram("two_qubit_DJ", platf_cfg)

    # experiments
    # 1
    k = p.create_kernel("DJ1")
    k.prepz(q0)  # to ensure enough separation in timing
    k.prepz(q1)  # to ensure enough separation in timing
    # prerotations
    k.gate('ry90', [q0])
    k.gate('rym90', [q1])
    # post rotations
    k.gate('ry90', [q0])
    k.gate('ry90', [q1])
    # measure
    k.measure(q0)
    k.measure(q1)
    p.add_kernel(k)

    # 2
    k = p.create_kernel("DJ2")
    k.prepz(q0)  # to ensure enough separation in timing
    k.prepz(q1)  # to ensure enough separation in timing
    # prerotations
    k.gate('ry90', [q0])
    k.gate('rym90', [q1])
    # rotations
    k.gate('rx180', [q1])
    # post rotations
    k.gate('ry90', [q0])
    k.gate('ry90', [q1])
    # measure
    k.measure(q0)
    k.measure(q1)
    p.add_kernel(k)

    # 3
    k = p.create_kernel("DJ3")
    k.prepz(q0)  # to ensure enough separation in timing
    k.prepz(q1)  # to ensure enough separation in timing
    # prerotations
    k.gate('ry90', [q0])
    k.gate('rym90', [q1])
    # rotations
    k.gate('ry90', [q1])
    k.gate('rx180', [q0])
    k.gate('rx180', [q1])

    # Hardcoded flux pulse, FIXME use actual CZ
    k.barrier([])  # alignment workaround
    k.gate('wait', [2, 0], 100)
    k.gate('fl_cw_01', [2, 0])
    # FIXME hardcoded extra delays
    k.gate('wait', [2, 0], 200)
    k.barrier([])  # alignment workaround

    k.gate('rx180', [q0])
    k.gate('ry90', [q1])

    # post rotations
    k.gate('ry90', [q0])
    k.gate('ry90', [q1])
    # measure
    k.measure(q0)
    k.measure(q1)
    p.add_kernel(k)

    # 4
    k = p.create_kernel("DJ4")
    k.prepz(q0)  # to ensure enough separation in timing
    k.prepz(q1)  # to ensure enough separation in timing
    # prerotations
    k.gate('ry90', [q0])
    k.gate('rym90', [q1])
    # rotations
    k.gate('rym90', [q1])
    # Hardcoded flux pulse, FIXME use actual CZ
    k.barrier([])  # alignment workaround
    k.gate('wait', [2, 0], 100)
    k.gate('fl_cw_01', [2, 0])
    # FIXME hardcoded extra delays
    k.gate('wait', [2, 0], 200)
    k.barrier([])  # alignment workaround

    k.gate('rx180', [q1])
    k.gate('rym90', [q1])

    # post rotations
    k.gate('ry90', [q0])
    k.gate('ry90', [q1])
    # measure
    k.measure(q0)
    k.measure(q1)
    p.add_kernel(k)

    # 7 repetitions is because of assumptions in tomo analysis
    p.add_two_q_cal_points(q0=q0, q1=q1, reps_per_cal_pt=7)
    p.compile()
    return p


def single_qubit_parity_check(
        qD: int,
        qA: int,
        platf_cfg: str,
        number_of_repetitions: int = 10,
        initialization_msmt: bool = False,
        initial_states=['0', '1'],
        flux_codeword: str = 'cz',
        parity_axis='Z'
) -> OqlProgram:
    """
    Implements a circuit for repeated parity checks.

    Circuit looks as follows:

    Data    (M)|------0------- | ^N- M
 M
               |      |        |
    Ancilla (M)|-my90-0-y90-M- |   - M
    The initial "M" measurement is optional, the circuit is repated N times
    At the end both qubits are measured.

    Arguments:
        qD :        Data qubit, this is the qubit that the repeated parity
                    check will be performed on.
        qA :        Ancilla qubit, qubit that the parity will be mapped onto.
        platf_cfg:  filename of the platform config file
        number_of_repetitions: number of times to repeat the circuit
        initialization_msmt : whether to start with an initial measurement
                    to prepare the starting state.
    """
    p = OqlProgram("single_qubit_repeated_parity_check", platf_cfg)

    for k, initial_state in enumerate(initial_states):
        k = p.create_kernel('repeated_parity_check_{}'.format(k))
        k.prepz(qD)
        k.prepz(qA)
        if initialization_msmt:
            k.measure(qA)
            k.measure(qD)
            k.barrier([])  # wait on all
        if initial_state == '1':
            k.gate('ry180', [qD])
        elif initial_state == '+':
            k.gate('ry90', [qD])
        elif initial_state == '-':
            k.gate('rym90', [qD])
        elif initial_state == 'i':
            k.gate('rx90', [qD])
        elif initial_state == '-i':
            k.gate('rxm90', [qD])
        elif initial_state == '0':
            pass
        else:
            raise ValueError('initial_state= ' + initial_state + ' not recognized')
        for i in range(number_of_repetitions):
            k.gate('rym90', [qA])
            if parity_axis == 'X':
                k.gate('rym90', [qD])
            k.barrier([])  # alignment workaround
            k.gate(flux_codeword, [qA, qD])
            k.barrier([])  # alignment workaround
            k.gate('ry90', [qA])
            k.barrier([qA, qD])
            if parity_axis == 'X':
                k.gate('ry90', [qD])
            k.measure(qA)

        k.measure(qD)
        # hardcoded barrier because of openQL #104
        # k.gate('wait', [2, 0], 0)
        k.barrier([qA, qD])
        p.add_kernel(k)

    p.compile()
    return p


def two_qubit_parity_check(
        qD0: int, qD1: int, qA: int,
        platf_cfg: str,
        # echo: bool = False,
        number_of_repetitions: int = 10,
        initialization_msmt: bool = False,
        initial_states=[['0', '0'], ['0', '1'], ['1', '1', ], ['1', '0']],
        flux_codeword: str = 'cz',
        flux_codeword_list: List[str] = None,
        # flux_codeword_D1: str = None,
        parity_axes=['ZZ'],
        tomo=False,
        tomo_after=False,
        ro_time=500e-9,
        echo_during_ancilla_mmt: bool = False,
        idling_time: float = 40e-9,
        idling_time_echo: float = 20e-9,
        idling_rounds: int = 0
) -> OqlProgram:
    """
    Implements a circuit for repeated parity checks on two qubits.

    Circuit looks as follows:
                                                         ^N
    Data0   ----prep.|------0-------(wait) (echo) (wait)| (tomo) -MMMMMMMMMMMMMMMMMMMM
                     |      |                           |
    Ancilla (M)------|-my90-0-0-y90-MMMMMMMMMMMMMMMMMMMM|
                     |        |                         |
    Data1   ----prep.|--------0-----(wait) (echo) (wait)| (tomo) -MMMMMMMMMMMMMMMMMMMM


    The initial "M" measurement is optional, the circuit is repated N times
    At the end both qubits are measured.

    Arguments:
        qD0 :       Data qubit, this is the qubit that the repeated parity
                    check will be performed on.
        qD1 :       Data qubit, this is the qubit that the repeated parity
                    check will be performed on.
        exho:       additional pi-pulse between the CZs
        qA :        Ancilla qubit, qubit that the parity will be mapped onto.
        platf_cfg:  filename of the platform config file
        number_of_repetitions: number of times to repeat the circuit
        initialization_msmt : whether to start with an initial measurement
                    to prepare the starting state.
    """

    p = OqlProgram("two_qubit_parity_check", platf_cfg)
    data_qubits = [qD0, qD1]
    if tomo:
        tomo_gates = ['i', 'rx180', 'ry90', 'rym90', 'rx90', 'rxm90']
    else:
        tomo_gates = ['False']

    for p_q1 in tomo_gates:
        for p_q0 in tomo_gates:
            for initial_state in initial_states:
                k = p.create_kernel(
                    'repeated_parity_check_' + initial_state[0] + initial_state[
                        1] + '_tomo0_' + p_q0 + '_tomo1_' + p_q1)
                k.prepz(qD0)
                k.prepz(qD1)
                k.prepz(qA)

                # initialization
                if initialization_msmt:
                    k.barrier([])  # alignment workaround
                    # k.measure(qD0)
                    # k.measure(qD1)
                    k.measure(qA)
                    if echo_during_ancilla_mmt:
                        k.gate('wait', [qA, qD0, qD1], int(ro_time * 1e9))
                    k.gate('wait', [qD0, qD1, qA],
                           int(100))  # adding additional wait time to ensure good initialization
                    k.barrier([])  # alignment workaround

                # state preparation
                for i, initial_state_q in enumerate(initial_state):
                    if initial_state_q == '1':
                        k.gate('ry180', [data_qubits[i]])
                    elif initial_state_q == '+':
                        k.gate('ry90', [data_qubits[i]])
                    elif initial_state_q == '-':
                        k.gate('rym90', [data_qubits[i]])
                    elif initial_state_q == 'i':
                        k.gate('rx90', [data_qubits[i]])
                    elif initial_state_q == '-i':
                        k.gate('rxm90', [data_qubits[i]])
                    elif initial_state_q == '0':
                        pass
                    else:
                        raise ValueError('initial_state_q= ' + initial_state_q + ' not recognized')

                # parity measurement(s)
                for i in range(number_of_repetitions):
                    for parity_axis in parity_axes:
                        k.barrier([])  # alignment workaround
                        if parity_axis == 'XX':
                            k.gate('rym90', [qD0])
                            k.gate('rym90', [qD1])
                            k.barrier([])  # alignment workaround
                        if parity_axis == 'YY':
                            k.gate('rxm90', [qD0])
                            k.gate('rxm90', [qD1])
                            k.barrier([])  # alignment workaround
                        k.gate('rym90', [qA])
                        # k.gate('ry90', [qD0])
                        # k.gate('ry90', [qD1])

                        # fluxing
                        k.barrier([])  # alignment workaround
                        # k.gate(flux_codeword, [qA, qD1])
                        if flux_codeword_list:
                            for flcw in flux_codeword_list:
                                k.gate(flcw, [0])
                        else:
                            k.gate(flux_codeword, [qA, qD0])
                            k.barrier([])
                            # if echo:
                            #     k.gate('ry180', [qA])
                            k.gate(flux_codeword, [qA, qD1])
                        k.barrier([])  # alignment workaround

                        k.gate('ry90', [qA])
                        # k.gate('rym90', [qD0])
                        # k.gate('rym90', [qD1])
                        k.barrier([])
                        if parity_axis == 'XX':
                            k.gate('ry90', [qD0])
                            k.gate('ry90', [qD1])
                            k.barrier([])  # alignment workaround
                        elif parity_axis == 'YY':
                            k.gate('rx90', [qD0])
                            k.gate('rx90', [qD1])
                            k.barrier([])  # alignment workaround
                        if (i is not number_of_repetitions - 1) or (tomo_after):  # last mmt can be multiplexed
                            k.barrier([])
                            k.measure(qA)
                            if echo_during_ancilla_mmt:
                                k.gate('ry180', [qD0])
                                k.gate('ry180', [qD1])
                                k.gate('wait', [qA, qD0, qD1], int(ro_time * 1e9))
                k.barrier([])  # separating parity from tomo

                if idling_rounds != 0:
                    for j in np.arange(idling_rounds):
                        k.gate("wait", [], int(idling_time_echo * 1e9))  # alignment workaround
                        if echo_during_ancilla_mmt:
                            k.gate('ry180', [qD0])
                            k.gate('ry180', [qD1])
                        k.gate("wait", [], int((idling_time - idling_time_echo - 20e-9) * 1e9))  # alignment workaround

                # tomography
                if tomo:
                    k.barrier([qD1, qD0])  # alignment workaround
                    k.gate(p_q0, [qD1])
                    k.gate(p_q1, [qD0])
                    k.barrier([qD1, qD0])  # alignment workaround
                # else:
                #     # flip data qubits before measurement
                #     for i, initial_state_q in enumerate(initial_state):
                #         if initial_state_q == '1':
                #             k.gate('ry180', [data_qubits[i]])
                #         elif initial_state_q == '+':
                #             k.gate('ry90', [data_qubits[i]])
                #         elif initial_state_q == '-':
                #             k.gate('rym90', [data_qubits[i]])
                #         elif initial_state_q == 'i':
                #             k.gate('rx90', [data_qubits[i]])
                #         elif initial_state_q == '-i':
                #             k.gate('rxm90', [data_qubits[i]])
                #         elif initial_state_q == '0':
                #             pass
                #         else:
                #             raise ValueError('initial_state_q= '+initial_state_q+' not recognized')

                # measure
                if not tomo_after:
                    k.barrier([])  # alignment workaround
                    k.measure(qA)
                k.measure(qD0)
                k.measure(qD1)
                p.add_kernel(k)

    if tomo:
        # only add calibration points when doing tomography
        interleaved_delay = ro_time
        if echo_during_ancilla_mmt:
            interleaved_delay = ro_time
        if tomo_after:
            p.add_two_q_cal_points(
                q0=qD0, q1=qD1,
                reps_per_cal_pt=7,
                measured_qubits=[qD0, qD1],
                interleaved_measured_qubits=[qA],
                interleaved_delay=interleaved_delay,
                nr_of_interleaves=initialization_msmt + number_of_repetitions * len(parity_axes))

        else:
            p.add_two_q_cal_points(
                q0=qD0, q1=qD1,
                reps_per_cal_pt=7,
                measured_qubits=[qD0, qD1, qA],
                interleaved_measured_qubits=[qA],
                interleaved_delay=interleaved_delay,
                nr_of_interleaves=initialization_msmt + number_of_repetitions * len(parity_axes) - 1)

    p.compile()
    return p


def conditional_oscillation_seq(
        q0: int, q1: int,
        q2: int = None, q3: int = None,
        platf_cfg: str = None,
        disable_cz: bool = False,
        disabled_cz_duration: int = 40,
        cz_repetitions: int = 1,
        angles=np.arange(0, 360, 20),
        wait_time_before_flux: int = 0,
        wait_time_after_flux: int = 0,
        add_cal_points: bool = True,
        cases: list = ('no_excitation', 'excitation'),
        flux_codeword: str = 'cz',
        flux_codeword_park: str = None,
        parked_qubit_seq: str = 'ground',
        disable_parallel_single_q_gates: bool = False
) -> OqlProgram:
    '''
    Sequence used to calibrate flux pulses for CZ gates.

    q0 is the oscillating qubit
    q1 is the spectator qubit

    Timing of the sequence:
    q0:  X90   --  C-Phase  (repet. C-Phase) Rphi90 RO
    q1: X180/I --  C-Phase         --        X180   RO
    q2:  X90   -- PARK/C-Phase     --        Rphi90 RO
    q3: X180/I --  C-Phase         --        X180   RO

    Args:
        q0, q1      (str): names of the addressed qubits
        q2, q3      (str): names of optional extra qubit to either park or
            apply a CZ to.

        flux_codeword (str):
            the gate to be applied to the qubit pair q0, q1
        flux_codeword_park (str):
            optionally park qubits q2 (and q3) with either a 'park' pulse
            (single qubit operation on q2) or a 'cz' pulse on q2-q3.
        disable_cz (bool): disable CZ gate
        cz_repetitions (int): how many cz gates to apply consecutively
        angles      (array): angles of the recovery pulse
        wait_time_after_flux   (int): wait time in ns after triggering all flux
            pulses
    '''
    assert parked_qubit_seq in {"ground", "ramsey", "excited"}

    p = OqlProgram("conditional_oscillation_seq", platf_cfg)

    # These angles correspond to special pi/2 pulses in the lutman
    for i, angle in enumerate(angles):
        for case in cases:

            k = p.create_kernel("{}_{}".format(case, angle))
            k.prepz(q0)
            k.prepz(q1)
            if q2 is not None:
                k.prepz(q2)
            if q3 is not None:
                k.prepz(q3)

            k.barrier([])  # alignment workaround

            # #################################################################
            # Single qubit ** parallel ** gates before flux pulses
            # #################################################################

            control_qubits = [q1]
            if q3 is not None:
                # In case of parallel cz
                control_qubits.append(q3)

            ramsey_qubits = [q0]
            if q2 is not None:
                if parked_qubit_seq == "ramsey":
                    # For parking and parallel cz
                    ramsey_qubits.append(q2)
                elif parked_qubit_seq == "excited":
                    k.gate("rx180", [q2])

            if q3 is not None:
                if parked_qubit_seq == "ramsey":
                    # For parking and parallel cz
                    ramsey_qubits.append(q3)
                elif parked_qubit_seq == "excited":
                    k.gate("rx180", [q3])

            if case == "excitation":
                # implicit identities otherwise
                for q in control_qubits:
                    k.gate("rx180", [q])
                    if disable_parallel_single_q_gates:
                        k.barrier([])

            for q in ramsey_qubits:
                k.gate("rx90", [q])
                if disable_parallel_single_q_gates:
                    k.barrier([])

            k.barrier([])  # alignment workaround

            # #################################################################
            # Flux pulses
            # #################################################################

            k.gate('wait', [], wait_time_before_flux)

            for dummy_i in range(cz_repetitions):
                if not disable_cz:
                    # Parallel flux pulses below
                    if 'dance' in flux_codeword:
                        k.gate(flux_codeword, [0])

                    elif 'parity_check' in flux_codeword:
                        k.gate(f'flux_dance_refocus_1', [0])
                        k.gate(f'flux_dance_refocus_2', [0])
                        k.gate(f'flux_dance_refocus_3', [0])
                        k.gate(f'flux_dance_refocus_4', [0])
                    else:
                        k.gate(flux_codeword, [q0, q1])
                    

                    k.barrier([q0, q1])

                    # in case of parking and parallel cz
                    if flux_codeword_park == 'cz':
                        k.gate(flux_codeword_park, [q2, q3])
                    elif flux_codeword_park == 'park':
                        k.gate(flux_codeword_park, [q2])
                        if q3 is not None:
                            raise ValueError("Expected q3 to be None")
                    elif flux_codeword_park is None:
                        pass
                    else:
                        raise ValueError(
                            'flux_codeword_park "{}" not allowed'.format(
                                flux_codeword_park))
                else:
                    k.barrier([])  # alignment workaround
                    # k.gate('wait', [q0,q1], wait_time_between + CZ_duration)
                    k.gate('wait', [q0, q1], disabled_cz_duration)
                    k.barrier([])  # alignment workaround

                k.barrier([])

            k.gate('wait', [], wait_time_after_flux)

            # #################################################################
            # Single qubit ** parallel ** gates post flux pulses
            # #################################################################
            if case == "excitation":
                for q in control_qubits:
                    k.gate("rx180", [q])
                    if disable_parallel_single_q_gates:
                        k.barrier([])

            # cw_idx corresponds to special hardcoded angles in the lutman
            # special because the cw phase pulses go in mult of 20 deg
            cw_idx = angle // 20 + 9
            phi_gate = None
            if angle == 90:
                phi_gate = 'ry90'
            elif angle == 0:
                phi_gate = 'rx90'
            else:
                phi_gate = 'cw_{:02}'.format(cw_idx)

            for q in ramsey_qubits:
                k.gate(phi_gate, [q])
                if disable_parallel_single_q_gates:
                    k.barrier([])

            if q2 is not None and parked_qubit_seq == "excited":
                k.gate("rx180", [q2])
            if q3 is not None and parked_qubit_seq == "excited":
                k.gate("rx180", [q3])

            k.barrier([])

            # #################################################################
            # Measurement
            # #################################################################
            k.measure(q0)
            k.measure(q1)
            if q2 is not None:
                k.measure(q2)
            if q3 is not None:
                k.measure(q3)
            k.barrier([])
            p.add_kernel(k)

    if add_cal_points:
        if q2 is None:
            states = ["00", "01", "10", "11"]
        else:
            states = ["000", "010", "101", "111"]

        qubits = [q0, q1] if q2 is None else [q0, q1, q2]
        p.add_multi_q_cal_points(
            qubits=qubits,
            f_state_cal_pt_cw=31,
            combinations=states)

    p.compile()

    # [2020-06-24] parallel cz not supported (yet)

    if add_cal_points:
        cal_pts_idx = np.arange(0,len(states))+361
    else:
        cal_pts_idx = []

    p.sweep_points = np.concatenate(
        [np.repeat(angles, len(cases)), cal_pts_idx])

    return p


def conditional_oscillation_seq_multi(
        Q_idxs_target,
        Q_idxs_control,
        Q_idxs_parked: List[int] = None,
        platf_cfg: str = None,
        disable_cz: bool = False,
        disabled_cz_duration: int = 60,
        cz_repetitions: int = 1,
        angles=np.arange(0, 360, 20),
        wait_time_before_flux: int = 0,
        wait_time_after_flux: int = 0,
        add_cal_points: bool = True,
        cases: list = ('no_excitation', 'excitation'),
        flux_codeword: str = 'cz',
        parked_qubit_seq: str = 'ground', # 'ramsey', 'excited'
        disable_parallel_single_q_gates: bool = False
        ):
    '''
    Sequence used to calibrate flux pulses for CZ gates.

    Pairs : contains all the gates gates with q0 is the target and q1 is the control.

    parking qbs: includes all qubits to be parked.

    Timing of the sequence:
    q0:  X90   --  C-Phase  (repet. C-Phase) Rphi90 RO
    q1: X180/I --  C-Phase         --        X180   RO
    p1:  X90   -- PARK/C-Phase     --        Rphi90 RO
    p2: X180/I --  C-Phase         --        X180   RO

    Args:
         pairs : contains all the gates gates with q0 is the target and q1 is the control.

        parking qbs: includes all qubits to be parked.

        flux_codeword (str):
            the gate to be applied to the qubit pair q0, q1
        flux_codeword_park (str):
            optionally park qubits q2 (and q3) with either a 'park' pulse
            (single qubit operation on q2) or a 'cz' pulse on q2-q3.
        disable_cz (bool): disable CZ gate
        cz_repetitions (int): how many cz gates to apply consecutively
        angles      (array): angles of the recovery pulse
        wait_time_after_flux   (int): wait time in ns after triggering all flux
            pulses
    '''
    p = OqlProgram("conditional_oscillation_seq_multi", platf_cfg)

    # These angles correspond to special pi/2 pulses in the lutman
    for i, angle in enumerate(angles):
        for case in cases:

            k = p.create_kernel("{}_{}".format(case, angle))

            for q0 in Q_idxs_target:
                k.prepz(q0)
            for q1 in Q_idxs_control:
                k.prepz(q1)
            if Q_idxs_parked:
                for qp in Q_idxs_parked:
                    k.prepz(qp)
            k.gate("wait", [], 0)  # alignment workaround

            # #################################################################
            # Single qubit ** parallel ** gates before flux pulses
            # #################################################################

            # Q_idxs_target = [q0]
            # if q2 is not None and parked_qubit_seq == "ramsey":
            #     # For parking and parallel cz
            #     Q_idxs_target.append(q2)

            if case == "excitation":
                # implicit identities otherwise
                for q1 in Q_idxs_control:
                    k.gate("rx180", [q1])

            for q0 in Q_idxs_target:
                k.gate("rx90", [q0])

            if parked_qubit_seq == "ramsey":
                for qp in Q_idxs_parked:
                    k.gate("rx90", [qp])
            elif parked_qubit_seq == "excited":
                for qp in Q_idxs_parked:
                    k.gate("rx180", [qp])

            k.barrier([])  # alignment workaround

            # #################################################################
            # Flux pulses
            # #################################################################

            k.gate('wait', [], wait_time_before_flux)

            for dummy_i in range(cz_repetitions):
                if not disable_cz:
                    # Parallel flux pulses below
                    if flux_codeword is 'cz':
                        for q0, q1 in zip(Q_idxs_target, Q_idxs_control):
                            k.gate(flux_codeword, [q0, q1])
                    else:
                        k.gate(flux_codeword, [0])
                        # k.gate('sf_cz_ne', [3])
                        # k.gate('sf_cz_ne', [8])
                        # k.gate('sf_cz_ne', [11])
                        # k.gate('sf_cz_sw', [5])
                        # k.gate('sf_cz_sw', [16])
                        # k.gate('sf_cz_sw', [2])
                        # k.gate('sf_park', [1])
                        # k.gate('sf_park', [6])
                        # k.gate('sf_park', [10])
                        # k.gate('sf_park', [14])

                else:
                    for q0, q1 in zip(Q_idxs_target, Q_idxs_control):
                        k.gate('wait', [q0, q1], disabled_cz_duration)
                k.gate("wait", [], 0)

            k.gate('wait', [], wait_time_after_flux)

            # #################################################################
            # Single qubit ** parallel ** gates post flux pulses
            # #################################################################

            if case == "excitation":
                for q_idx in Q_idxs_control:
                    k.gate("rx180", [q_idx])

            # cw_idx corresponds to special hardcoded angles in the lutman
            # special because the cw phase pulses go in mult of 20 deg
            cw_idx = angle // 20 + 9
            phi_gate = None
            phi_gate = 'cw_{:02}'.format(cw_idx)

            for q_idx in Q_idxs_target:
                k.gate(phi_gate, [q_idx])

            if parked_qubit_seq == "ramsey":
                for qp in Q_idxs_parked:
                    k.gate(phi_gate, [qp])
            elif parked_qubit_seq == "excited":
                for qp in Q_idxs_parked:
                    k.gate("rx180", [qp])
            k.gate('wait', [], 0)

            # #################################################################
            # Measurement
            # #################################################################

            for q0 in Q_idxs_target:
                k.measure(q0)
            for q1 in Q_idxs_control:
                k.measure(q1)
            if parked_qubit_seq == "ramsey" or parked_qubit_seq == "excited":
                for qp in Q_idxs_parked:
                    k.measure(qp)
            k.barrier([])

            p.add_kernel(k)

    if add_cal_points:
        n = len(Q_idxs_target)
        states = ["0" * n + "0" * n, "0" * n + "1" * n, "1" * n + "0" * n, "1" * n + "1" * n]

        qubits = Q_idxs_target + Q_idxs_control
        p.add_multi_q_cal_points(
            qubits=qubits,
            f_state_cal_pt_cw=31,
            combinations=states)

    p.compile()

    if add_cal_points:
        cal_pts_idx = [361, 362, 363, 364]
    else:
        cal_pts_idx = []

    p.sweep_points = np.concatenate(
        [np.repeat(angles, len(cases)), cal_pts_idx])

    return p


def parity_check_flux_dance(
        Q_idxs_target: List[int],
        Q_idxs_control: List[int],
        control_cases: List[str],
        flux_cw_list: List[str],
        Q_idxs_ramsey: List[int] = None,
        Q_idxs_parking: List[int] = None,
        nr_flux_dance_before_cal_points: int = None,
        platf_cfg: str = None,
        angles: np.ndarray = np.arange(0, 360, 20),
        initialization_msmt: bool = False,
        wait_time_before_flux: int = 0,
        wait_time_after_flux: int = 0,
        add_cal_points: bool = True
    ):
    '''
    TODO: this is currently X parity check, add parameter for X/Z type
    Sequence used to calibrate flux pulses for CZ gates.

    Pairs : contains all the gates gates with q0 is the target and q1 is the control.

    parking qbs: includes all qubits to be parked.

    Timing of the sequence:
    q0:  X90   --  C-Phase  (repet. C-Phase) Rphi90 RO
    q1: X180/I --  C-Phase         --        X180   RO
    p1:  X90   -- PARK/C-Phase     --        Rphi90 RO
    p2: X180/I --  C-Phase         --        X180   RO

    Args:
         pairs : contains all the gates gates with q0 is the target and q1 is the control.

        parking qbs: includes all qubits to be parked.

        flux_codeword (str):
            the gate to be applied to the qubit pair q0, q1
        flux_codeword_park (str):
            optionally park qubits q2 (and q3) with either a 'park' pulse
            (single qubit operation on q2) or a 'cz' pulse on q2-q3.
        disable_cz (bool): disable CZ gate
        cz_repetitions (int): how many cz gates to apply consecutively
        angles      (array): angles of the recovery pulse
        wait_time_after_flux   (int): wait time in ns after triggering all flux
            pulses
    '''
    p = OqlProgram("parity_check_flux_dance", platf_cfg)

    for case in control_cases:

        for i, angle in enumerate(angles):
            k = p.create_kernel("{}_{}".format(case, angle))

            for q0 in Q_idxs_target:
                k.prepz(q0)
            for q1 in Q_idxs_control:
                k.prepz(q1)
            if Q_idxs_parking:
                for q2 in Q_idxs_parking:
                    k.prepz(q2)
            k.barrier([])

            if initialization_msmt:
                for qD in Q_idxs_control:
                    k.measure(qD)
                for qA in Q_idxs_target:
                    k.measure(qA)
            k.barrier([])

            for i, indx in enumerate(case):
                if indx == '1':
                    k.gate("rx180", [Q_idxs_control[i]])

            for qb in Q_idxs_target:
                k.gate("rx90", [qb])

            if Q_idxs_ramsey:
                for qb in Q_idxs_ramsey:
                    k.gate("rx90", [qb])

            if Q_idxs_parking:
                for qb in Q_idxs_parking:
                    k.gate("rx180", [qb])

            k.barrier([])  # alignment workaround

            # #################################################################
            # Flux pulses
            # #################################################################
            # k.gate('wait', [], wait_time_before_flux)

            for flux_cw in flux_cw_list:
                k.gate(flux_cw, [0])
            k.barrier([])

            # k.gate('wait', [], wait_time_after_flux)
            # #################################################################
            # Single qubit gates post flux pulses
            # #################################################################
            for i, indx in enumerate(case):
                if indx == '1':
                    k.gate("rxm180", [Q_idxs_control[i]])

            # cw_idx corresponds to special hardcoded angles in the lutman
            # special because the cw phase pulses go in mult of 20 deg
            cw_idx = angle // 20 + 9
            phi_gate = None
            phi_gate = 'cw_{:02}'.format(cw_idx)

            for qb in Q_idxs_target:
                k.gate(phi_gate, [qb])

            if Q_idxs_ramsey:
                for qb in Q_idxs_ramsey:
                    k.gate("rxm90", [qb])

            if Q_idxs_parking:
                for qb in Q_idxs_parking:
                    k.gate("rxm180", [qb])

            k.barrier([])

            # #################################################################
            # Measurement
            # #################################################################
            for q0 in Q_idxs_target:
                k.measure(q0)
            for q1 in Q_idxs_control:
                k.measure(q1)
            if Q_idxs_parking:
                for q2 in Q_idxs_parking:
                    k.measure(q2)
            k.barrier([])

            p.add_kernel(k)

    if add_cal_points:
        qubits = Q_idxs_target + Q_idxs_control
        cal_states = ['{:0{}b}'.format(i, len(qubits)) for i in range(2 ** len(qubits))]

        # add calibration points for separately measured parking qubits,
        # such that the first half of calibration states by case will have
        # the parked qubits appended in state 0, and the second half in state 1
        if Q_idxs_parking:
            cal_states = [state + '0' if i < len(cal_states) / 2 else state + '1' for i, state in enumerate(cal_states)]

        p.add_multi_q_cal_points(
            qubits=qubits if not Q_idxs_parking else qubits + Q_idxs_parking,
            f_state_cal_pt_cw=31,
            combinations=cal_states,
            nr_flux_dance=nr_flux_dance_before_cal_points,
            flux_cw_list=flux_cw_list if nr_flux_dance_before_cal_points else None
        )

    p.compile()

    if add_cal_points:
        cal_pts_idx = np.arange(len(control_cases), len(cal_states) + len(control_cases))
    else:
        cal_pts_idx = []

    p.sweep_points = np.concatenate([np.repeat(np.arange(len(control_cases)), len(angles)),
                                     cal_pts_idx])

    return p


def parity_check_fidelity(
        Q_idxs_target: List[str],
        Q_idxs_control: List[str],
        control_cases: List[str],
        flux_cw_list: List[str],
        Q_idxs_ramsey: List[str] = None,
        refocusing: bool = False,
        initialization_msmt: bool = False,
        wait_time_before_flux: int = 0,
        wait_time_after_flux: int = 0,
        platf_cfg: str = None
        ):
    '''
    TODO: this is currently X parity check, add parameter for X/Z type
    Sequence used to calibrate flux pulses for CZ gates.

    Pairs : contains all the gates gates with q0 is the target and q1 is the control.

    parking qbs: includes all qubits to be parked.

    Timing of the sequence:
    q0:  X90   --  C-Phase  (repet. C-Phase) Rphi90 RO
    q1: X180/I --  C-Phase         --        X180   RO
    p1:  X90   -- PARK/C-Phase     --        Rphi90 RO
    p2: X180/I --  C-Phase         --        X180   RO

    Args:
         pairs : contains all the gates gates with q0 is the target and q1 is the control.

        parking qbs: includes all qubits to be parked.

        flux_codeword (str):
            the gate to be applied to the qubit pair q0, q1
        flux_codeword_park (str):
            optionally park qubits q2 (and q3) with either a 'park' pulse
            (single qubit operation on q2) or a 'cz' pulse on q2-q3.
        disable_cz (bool): disable CZ gate
        cz_repetitions (int): how many cz gates to apply consecutively
        angles      (array): angles of the recovery pulse
        wait_time_after_flux   (int): wait time in ns after triggering all flux
            pulses
    '''
    p = OqlProgram("parity_check_fidelity", platf_cfg)

    for case in control_cases:

        k = p.create_kernel("{}".format(case))

        # #################################################################
        # State preparation
        # #################################################################
        for qb in Q_idxs_target + Q_idxs_control:
            k.prepz(qb)
        k.barrier([])

        if initialization_msmt:
            for qb in Q_idxs_target + Q_idxs_control:
                k.measure(qb)
            k.gate("wait", [], 0)

        for i, indx in enumerate(case):
            if indx == '1':
                k.gate("rx180", [Q_idxs_control[i]])

        for qb in Q_idxs_target:
            k.gate("rxm90", [qb])

        if Q_idxs_ramsey:
            for qb in Q_idxs_ramsey:
                k.gate("rxm90", [qb])

        k.barrier([])  # alignment workaround

        # #################################################################
        # Flux pulses
        # #################################################################
        k.gate('wait', [], wait_time_before_flux)

        for flux_cw in flux_cw_list:
            k.gate(flux_cw, [0])
        k.barrier([])

        k.gate('wait', [], wait_time_after_flux)
        # #################################################################
        # Single qubit gates post flux pulses
        # #################################################################
        for i, indx in enumerate(case):
            if indx == '1':
                k.gate("rxm180", [Q_idxs_control[i]])

        for q_idx in Q_idxs_target:
            k.gate("cw_09", [q_idx])

        if Q_idxs_ramsey:
            for qb in Q_idxs_ramsey:
                k.gate("rx90", [qb])

        k.barrier([])
        # #################################################################
        # Measurement
        # #################################################################

        for qb in Q_idxs_target + Q_idxs_control:
            k.measure(qb)

        p.add_kernel(k)

    p.compile()

    return p

def Weight_4_parity_tomography(
        Q_anc: int,
        Q_D1: int,
        Q_D2: int,
        Q_D3: int,
        Q_D4: int,
        platf_cfg: str,
        simultaneous_measurement: bool=True
        ):
    p = OqlProgram("Weight_4_parity_tomography", platf_cfg)
    all_Q_idxs = [Q_anc, Q_D1, Q_D2, Q_D3, Q_D4]
    tomo_gates = {'Z': 'i', 'X': 'rym90', 'Y': 'rx90'}

    for op1, g1 in tomo_gates.items():
        for op2, g2 in tomo_gates.items():
            for op3, g3 in tomo_gates.items():
                for op4, g4 in tomo_gates.items():

                    k = oqh.create_kernel(f'Tomo_{op1+op2+op3+op4}', p)

                    for q in all_Q_idxs:
                        k.prepz(q)
                        k.gate("ry90", [q])

                    k.gate("wait", [], 0)
                    k.gate("flux-dance-1-refocus", [0])
                    k.gate("flux-dance-2-refocus", [0])
                    k.gate("flux-dance-3-refocus", [0])
                    k.gate("flux-dance-4-refocus", [0])
                    k.gate("wait", [], 0)

                    for q in all_Q_idxs:
                        k.gate("rym90", [q])
                    k.gate("wait", [], 0)

                    k.measure(Q_anc)

                    if not simultaneous_measurement:
                        k.gate("cw_30", [2])
                        k.gate('wait', [2], 360)
                        k.gate("cw_30", [0])
                        k.gate('wait', [0], 380)
                        k.gate("cw_30", [13])
                        k.gate('wait', [13], 280)
                        k.gate("cw_30", [16])
                        k.gate('wait', [16], 320)
                        k.gate("wait", [], 0)

                    for q, g in zip([Q_D1, Q_D2, Q_D3, Q_D4], [g1, g2, g3, g4]):
                        k.gate(g, [q])
                        k.measure(q)
                    k.gate("wait", [], 0)

                    if not simultaneous_measurement:
                        k.measure(Q_D4)

                    p.add_kernel(k)

    # Calibration points
    combinations = [ s1+s2+s3+s4+s5  for s1 in ['0', '1']
                                     for s2 in ['0', '1']
                                     for s3 in ['0', '1']
                                     for s4 in ['0', '1']
                                     for s5 in ['0', '1'] ]
    oqh.add_multi_q_cal_points(p,
                               qubits=[Q_anc, Q_D1, Q_D2, Q_D3, Q_D4],
                               combinations=combinations,
                               reps_per_cal_pnt=1)
    p = oqh.compile(p)
    return p

def Parity_Sandia_benchmark(
        qA: int,
        QDs: list,
        platf_cfg: str = None):
      '''
      Sandia's weight-4 parity check benchmark protocol.
      '''
      delays = {}
      p = OqlProgram("Sandia_parity_benchmark", platf_cfg)

      # lb = ["P_0000","P_1111","Single_parity_check","Double_parity_check"]
      # for i,ks in enumerate(lb):

      k = p.create_kernel("P_0000")
      all_q_idxs = QDs+[qA]
      for q_idx in all_q_idxs:
            k.prepz(q_idx)
            k.measure(q_idx)
      p.add_kernel(k)
      
      k = p.create_kernel("P_1111")
      all_q_idxs = QDs+[qA]
      for q_idx in all_q_idxs:
            k.prepz(q_idx)
            k.gate("rx180", [q_idx])
            k.measure(q_idx)
      p.add_kernel(k)
      
      k = p.create_kernel("Single_parity_check")
      all_q_idxs = QDs+[qA]
      for q_idx in all_q_idxs:
            k.prepz(q_idx)
            k.gate("ry90", [q_idx])
      k.barrier([])
      k.gate("flux_dance_refocus_1", [0])
      k.gate("flux_dance_refocus_2", [0])
      k.gate("flux_dance_refocus_3", [0])
      k.gate("flux_dance_refocus_4", [0])
      k.barrier([])
      for q_idx in all_q_idxs:
            k.gate("rym90", [q_idx])
            k.measure(q_idx)
      p.add_kernel(k)


      k = p.create_kernel("Double_parity_check")
      all_q_idxs = QDs+[qA]
      for q_idx in all_q_idxs:
            k.prepz(q_idx)
            k.gate("ry90", [q_idx])
      k.barrier([])
      k.gate("flux_dance_refocus_1", [0])
      k.gate("flux_dance_refocus_2", [0])
      k.gate("flux_dance_refocus_3", [0])
      k.gate("flux_dance_refocus_4", [0])
      k.barrier([])
      for q_idx in all_q_idxs:
            k.gate("rym90", [q_idx])
      k.barrier([])
      k.measure(qA)

      # correct for msmt induced phaseshift on data qubits using phi-echo pulses
      k.gate("cw_30", [2])
      k.gate('wait', [2], 360)
      k.gate("cw_30", [0])
      k.gate('wait', [0], 380)
      k.gate("cw_30", [13])
      k.gate('wait', [13], 280)
      k.gate("cw_30", [16])
      k.gate('wait', [16], 320)
      k.barrier([])

      for q_idx in all_q_idxs:
            k.gate("ry90", [q_idx])
      k.barrier([])
      k.gate("flux_dance_refocus_1", [0])
      k.gate("flux_dance_refocus_2", [0])
      k.gate("flux_dance_refocus_3", [0])
      k.gate("flux_dance_refocus_4", [0])
      k.barrier([])
      for q_idx in all_q_idxs:
            k.gate("rym90", [q_idx])
            k.measure(q_idx)
      p.add_kernel(k)

      p.compile()

      return p

# FIXME: not really used, and partly uses hardcoded qubits
def grovers_two_qubit_all_inputs(
        q0: int, q1: int,
        platf_cfg: str,
        precompiled_flux: bool = True,
        second_CZ_delay: int = 0,
        CZ_duration: int = 260,
        add_echo_pulses: bool = False,
        cal_points: bool = True
) -> OqlProgram:
    """
    Writes the QASM sequence for Grover's algorithm on two qubits.
    Sequence:
        q0: G0 -       - mY90 -    - mY90  - RO
                 CZ_ij          CZ
        q1: G1 -       - mY90 -    - mY90  - RO
    whit all combinations of (ij) = omega.
    G0 and G1 are Y90 or Y90, depending on the (ij).

    Args:
        q0_name, q1_name (string):
                Names of the qubits to which the sequence is applied.
        RO_target (string):
                Readout target. Can be a qubit name or 'all'.
        precompiled_flux (bool):
                Determies if the full waveform for the flux pulses is
                precompiled, thus only needing one trigger at the start,
                or if every flux pulse should be triggered individually.
        add_echo_pulses (bool): if True add's echo pulses before the
            second CZ gate.
        cal_points (bool):
                Whether to add calibration points.

    Returns:
        qasm_file: a reference to the new QASM file object.
    """

    if not precompiled_flux:
        raise NotImplementedError('Currently only precompiled flux pulses '
                                  'are supported.')

    p = OqlProgram("grovers_two_qubit_all_inputs", platf_cfg)

    for G0 in ['ry90', 'rym90']:
        for G1 in ['ry90', 'rym90']:
            k = p.create_kernel('Gr{}_{}'.format(G0, G1))
            k.prepz(q0)
            k.prepz(q1)
            k.gate(G0, [q0])
            k.gate(G1, [q1])
            k.gate('fl_cw_03', [2, 0])  # flux cw03 is the multi_cz pulse
            k.gate('ry90', [q0])
            k.gate('ry90', [q1])
            # k.gate('fl_cw_00', 2,0)
            k.barrier([])  # alignment workaround
            k.gate('wait', [2, 0], second_CZ_delay // 2)
            k.barrier([])  # alignment workaround
            if add_echo_pulses:
                k.gate('rx180', [q0])
                k.gate('rx180', [q1])
            k.barrier([])  # alignment workaround
            k.gate('wait', [2, 0], second_CZ_delay // 2)
            k.barrier([])  # alignment workaround
            if add_echo_pulses:
                k.gate('rx180', [q0])
                k.gate('rx180', [q1])

            k.gate('wait', [2, 0], CZ_duration)

            k.gate('ry90', [q0])
            k.gate('ry90', [q1])
            k.measure(q0)
            k.measure(q1)
            k.barrier([2, 0])
            p.add_kernel(k)

    if cal_points:
        p.add_two_q_cal_points(q0=q0, q1=q1)
    p.compile()
    return p


def grovers_two_qubits_repeated(
        qubits,
        platf_cfg: str,
        nr_of_grover_iterations: int
) -> OqlProgram:
    """
    Writes the QASM sequence for Grover's algorithm on two qubits.
    Sequence:
        q0: G0 -       - mY90 -    - mY90  - RO
                 CZ             CZ
        q1: G1 -       - mY90 -    - mY90  - RO
    G0 and G1 are state preparation gates. Here G0 = 'ry90' and G1 = 'rym90'

    Parameters:
    -----------
    qubits: list of int
        List of the qubits (indices) to which the sequence is applied.
    """
    p = OqlProgram("grovers_two_qubits_repeated", platf_cfg)
    q0 = qubits[-1]
    q1 = qubits[-2]

    G0 = {"phi": 90, "theta": 90}
    G1 = {"phi": 90, "theta": 90}
    for i in range(nr_of_grover_iterations):
        # k = p.new_kernel('Grover_iteration_{}'.format(i))
        k = p.create_kernel('Grover_iteration_{}'.format(i))
        k.prepz(q0)
        k.prepz(q1)
        # k.prepz()
        k.gate('ry90', [q0])
        k.gate('ry90', [q1])
        # k.rotate(q0, **G0)
        # k.rotate(q1, **G1)

        for j in range(i):
            # Oracle stage
            k.gate('cz', [2, 0])  # hardcoded fixme
            # k.cz(q0, q1)
            # Tagging stage
            if (j % 2 == 0):
                k.gate('rym90', [q0])
                k.gate('rym90', [q1])
                # k.ry(q0, -90)
                # k.ry(q1, -90)
            else:
                k.gate('ry90', [q0])
                k.gate('ry90', [q1])
                # k.ry(q0, 90)
                # k.ry(q1, 90)
            k.gate('cz', [2, 0])  # hardcoded fixme
            # k.cz(q0, q1)
            if (j % 2 == 0):
                k.gate('ry90', [q0])
                k.gate('ry90', [q1])
            else:
                k.gate('rym90', [q0])
                k.gate('rym90', [q1])
            # if (j % 2 == 0):
            #     k.ry(q0, 90)
            #     k.ry(q1, 90)
            # else:
            #     k.ry(q0, -90)
            #     k.ry(q1, -90)
        k.measure(q0)
        k.measure(q1)
        p.add_kernel(k)
    p.compile()
    # p.compile()
    return p


# FIXME: not really used, and partly uses hardcoded qubits
def grovers_tomography(
        q0: int, q1: int,
        omega: int,
        platf_cfg: str,
        precompiled_flux: bool = True,
        # cal_points: bool = True,
        second_CZ_delay: int = 260,
        CZ_duration: int = 260,
        add_echo_pulses: bool = False
) -> OqlProgram:
    """
    Tomography sequence for Grover's algorithm.

        omega: int denoting state that the oracle prepares.
    """

    if not precompiled_flux:
        raise NotImplementedError('Currently only precompiled flux pulses '
                                  'are supported.')

    p = OqlProgram("grovers_tomography", platf_cfg)

    tomo_gates = ['i', 'rx180', 'ry90', 'rym90', 'rx90', 'rxm90']

    if omega == 0:
        G0 = 'ry90'
        G1 = 'ry90'
    elif omega == 1:
        G0 = 'ry90'
        G1 = 'rym90'
    elif omega == 2:
        G0 = 'rym90'
        G1 = 'ry90'
    elif omega == 3:
        G0 = 'rym90'
        G1 = 'rym90'
    else:
        raise ValueError('omega must be in [0, 3]')

    for p_q1 in tomo_gates:
        for p_q0 in tomo_gates:
            k = p.create_kernel('Gr{}_{}_tomo_{}_{}'.format(
                G0, G1, p_q0, p_q1))
            k.prepz(q0)
            k.prepz(q1)

            # Oracle
            k.gate(G0, [q0])
            k.gate(G1, [q1])
            k.gate('fl_cw_03', [2, 0])  # flux cw03 is the multi_cz pulse
            # Grover's search
            k.gate('ry90', [q0])
            k.gate('ry90', [q1])
            # k.gate('fl_cw_00', 2[,0])
            k.barrier([])  # alignment workaround
            k.gate('wait', [2, 0], second_CZ_delay // 2)
            k.barrier([])  # alignment workaround
            if add_echo_pulses:
                k.gate('rx180', [q0])
                k.gate('rx180', [q1])
            k.barrier([])  # alignment workaround
            k.gate('wait', [2, 0], second_CZ_delay // 2)
            k.barrier([])  # alignment workaround
            if add_echo_pulses:
                k.gate('rx180', [q0])
                k.gate('rx180', [q1])
            k.barrier([])  # alignment workaround
            k.gate('wait', [2, 0], CZ_duration)
            k.barrier([])  # alignment workaround
            k.gate('ry90', [q0])
            k.gate('ry90', [q1])

            # tomo pulses
            k.gate(p_q1, [q0])
            k.gate(p_q0, [q1])

            k.measure(q0)
            k.measure(q1)
            k.barrier([2, 0])
            p.add_kernel(k)

    p.add_two_q_cal_points(q0=q0, q1=q1, reps_per_cal_pt=7)
    p.compile()
    return p


# FIXME: used hardcoded qubits
def CZ_poisoned_purity_seq(
        q0, q1,
        platf_cfg: str,
        nr_of_repeated_gates: int,
        cal_points: bool = True
) -> OqlProgram:
    """
    Creates the |00> + |11> Bell state and does a partial tomography in
    order to determine the purity of both qubits.
    """
    p = OqlProgram("CZ_poisoned_purity_seq",
                   platf_cfg)
    tomo_list = ['rxm90', 'rym90', 'i']

    for p_pulse in tomo_list:
        k = p.create_kernel("{}".format(p_pulse))
        k.prepz(q0)
        k.prepz(q1)

        # Create a Bell state:  |00> + |11>
        k.gate('rym90', [q0])
        k.gate('ry90', [q1])
        k.barrier([])  # alignment workaround
        for i in range(nr_of_repeated_gates):
            k.gate('fl_cw_01', [2, 0])
        k.barrier([])  # alignment workaround
        k.gate('rym90', [q1])

        # Perform pulses to measure the purity of both qubits
        k.gate(p_pulse, [q0])
        k.gate(p_pulse, [q1])

        k.measure(q0)
        k.measure(q1)
        # Implements a barrier to align timings
        # k.gate('wait', [q0, q1], 0)
        # hardcoded because of openQL #104
        k.barrier([2, 0])

        p.add_kernel(k)

    if cal_points:
        # FIXME: replace with standard add cal points function
        k = p.create_kernel("Cal 00")
        k.prepz(q0)
        k.prepz(q1)
        k.measure(q0)
        k.measure(q1)
        k.barrier([2, 0])
        p.add_kernel(k)
        k = p.create_kernel("Cal 11")
        k.prepz(q0)
        k.prepz(q1)
        k.gate("rx180", [q0])
        k.gate("rx180", [q1])
        k.measure(q0)
        k.measure(q1)
        k.barrier([2, 0])
        p.add_kernel(k)

    p.compile()
    return p


def Chevron_first_manifold(
        qubit_idx: int,
        qubit_idx_spec: int,
        buffer_time,
        buffer_time2,
        flux_cw: int,
        platf_cfg: str
) -> OqlProgram:
    """
    Writes output files to the directory specified in openql.
    Output directory is set as an attribute to the program for convenience.

    Input pars:
        qubit_idx:      int specifying the target qubit (starting at 0)
        qubit_idx_spec: int specifying the spectator qubit
        buffer_time   :
        buffer_time2  :

        platf_cfg:      filename of the platform config file
    Returns:
        p:              OpenQL Program object containing

    """
    p = OqlProgram("Chevron_first_manifold", platf_cfg)

    buffer_nanoseconds = int(round(buffer_time / 1e-9))
    buffer_nanoseconds2 = int(round(buffer_time2 / 1e-9))
    if flux_cw is None:
        flux_cw = 2

    k = p.create_kernel("Chevron")
    k.prepz(qubit_idx)
    k.gate('rx180', [qubit_idx])
    k.gate("wait", [qubit_idx], buffer_nanoseconds)
    k.barrier([])  # alignment workaround
    k.gate('fl_cw_{:02}'.format(flux_cw), [2, 0])
    k.barrier([])  # alignment workaround
    k.gate('wait', [qubit_idx], buffer_nanoseconds2)
    k.measure(qubit_idx)
    k.measure(qubit_idx_spec)
    k.barrier([qubit_idx, qubit_idx_spec])
    p.add_kernel(k)

    p.compile()
    return p


def partial_tomography_cardinal(
        q0: int, q1: int,
        cardinal: int,
        platf_cfg: str,
        precompiled_flux: bool = True,
        # cal_points: bool = True,
        # second_CZ_delay: int = 260,
        # CZ_duration: int = 260,
        # add_echo_pulses: bool = False
) -> OqlProgram:
    """
    Tomography sequence for Grover's algorithm.

        cardinal: int denoting cardinal state prepared.
    """

    if not precompiled_flux:
        raise NotImplementedError('Currently only precompiled flux pulses '
                                  'are supported.')

    p = OqlProgram("partial_tomography_cardinal",
                   platf_cfg)

    cardinal_gates = ['i', 'rx180', 'ry90', 'rym90', 'rx90', 'rxm90']

    if (cardinal > 35 or cardinal < 0):
        raise ValueError('cardinal must be in [0, 35]')

    idx_p0 = cardinal % 6
    idx_p1 = ((cardinal - idx_p0) // 6) % 6
    # cardinal_gates[]
    # k.gate(string_of_the_gate, integer_from_qubit)
    tomo_gates = [('i', 'i'), ('i', 'rx180'), ('rx180', 'i'), ('rx180', 'rx180'),
                  ('ry90', 'ry90'), ('rym90', 'rym90'), ('rx90', 'rx90'), ('rxm90', 'rxm90')]

    for i_g, gates in enumerate(tomo_gates):
        idx_g0 = i_g % 6
        idx_g1 = ((i_g - idx_g0) // 6) % 6
        # strings denoting the gates
        SP0 = cardinal_gates[idx_p0]
        SP1 = cardinal_gates[idx_p1]
        t_q0 = gates[1]
        t_q1 = gates[0]
        k = p.create_kernel('PT_{}_tomo_{}_{}'.format(cardinal, idx_g0, idx_g1))

        k.prepz(q0)
        k.prepz(q1)

        # Cardinal state preparation
        k.gate(SP0, [q0])
        k.gate(SP1, [q1])
        # tomo pulses
        # to be taken from list of tuples
        k.gate(t_q1, [q0])
        k.gate(t_q0, [q1])

        k.measure(q0)
        k.measure(q1)
        k.barrier([])  # alignment workaround
        k.gate('wait', [2, 0], 0)
        k.barrier([])  # alignment workaround
        p.add_kernel(k)

    p.add_two_q_cal_points(q0=q0, q1=q1, reps_per_cal_pt=2)
    p.compile()
    return p


# FIXME: not really used
def two_qubit_VQE(q0: int, q1: int, platf_cfg: str) -> OqlProgram:
    """
    VQE tomography for two qubits.
    Args:
        cardinal        (int) : index of prep gate
        q0, q1          (int) : target qubits for the sequence
    """
    tomo_pulses = ['i', 'rx180', 'ry90', 'rym90', 'rx90', 'rxm90']
    tomo_list_q0 = tomo_pulses
    tomo_list_q1 = tomo_pulses

    p = OqlProgram("two_qubit_VQE", platf_cfg)

    # Tomography pulses
    i = 0
    for p_q1 in tomo_list_q1:
        for p_q0 in tomo_list_q0:
            i += 1
            kernel_name = '{}_{}_{}'.format(i, p_q0, p_q1)
            k = p.create_kernel(kernel_name)
            k.prepz(q0)
            k.prepz(q1)
            k.gate('ry180', [q0])  # Y180 gate without compilation
            k.gate('i', [q0])  # Y180 gate without compilation
            k.gate("wait", [q1], 40)
            k.barrier([])  # alignment workaround
            k.gate('fl_cw_02', [2, 0])
            k.barrier([])  # alignment workaround
            k.gate("wait", [q1], 40)
            k.gate(p_q0, [q0])  # compiled z gate+pre_rotation
            k.gate(p_q1, [q1])  # pre_rotation
            k.measure(q0)
            k.measure(q1)
            p.add_kernel(k)
    # every calibration point is repeated 7 times. This is copied from the
    # script for Tektronix driven qubits. I do not know if this repetition
    # is important or even necessary here.
    p.add_two_q_cal_points(q0=q1, q1=q0, reps_per_cal_pt=7)
    p.compile()
    return p


# FIXME: partly uses hardcoded qubits
def sliding_flux_pulses_seq(
        qubits: list,
        platf_cfg: str,
        angles=np.arange(0, 360, 20),
        wait_time: int = 0,
        flux_codeword_a: str = 'fl_cw_01',
        flux_codeword_b: str = 'fl_cw_01',
        ramsey_axis: str = 'x',
        add_cal_points: bool = True
) -> OqlProgram:
    """
    Experiment to measure effect flux pulses on each other.

    Timing of the sequence:
        q0:   -- flux_a -- wait -- X90 -- flux_b -- Rphi90 -- RO
        q1:   -- flux_a --      --     -- flux_b --        -- RO

    N.B. q1 only exists to satisfy flux tuples notion in CCL
    N.B.2 flux-tuples are now hardcoded to always be tuple [2,0] again
        because of OpenQL.

    Args:
        qubits      : list of qubits, LSQ (q0) is last entry in list
        platf_cfg   : openQL platform config
        angles      : angles along which to do recovery pulses
        wait_time   : time in ns after the first flux pulse and before the
            first microwave pulse.
        flux_codeword_a : flux codeword of the stimulus (1st) pulse
        flux_codeword_b : flux codeword of the spectator (2nd) pulse
        ramsey_axis : chooses between doing x90 or y90 rotation at the
            beginning of Ramsey sequence
        add_cal_points : if True adds calibration points at the end
    """

    p = OqlProgram("sliding_flux_pulses_seq", platf_cfg)
    k = p.create_kernel("sliding_flux_pulses_seq")
    q0 = qubits[-1]
    q1 = qubits[-2]

    for i, angle in enumerate(angles):
        cw_idx = angle // 20 + 9

        k.prepz(q0)
        k.gate(flux_codeword_a, [2, 0])  # edge hardcoded because of openql
        k.barrier([])  # alignment workaround
        # hardcoded because of flux_tuples, [q1, q0])
        k.gate('wait', [q0, q1], wait_time)

        if ramsey_axis == 'x':
            k.gate('rx90', [q0])
        elif ramsey_axis == 'y':
            k.gate('ry90', [q0])
        else:
            raise ValueError('ramsey_axis must be "x" or "y"')
        k.barrier([])  # alignment workaround
        k.gate(flux_codeword_b, [2, 0])  # edge hardcoded because of openql
        k.barrier([])  # alignment workaround
        k.gate('wait', [q0, q1], 60)
        # hardcoded because of flux_tuples, [q1, q0])
        # hardcoded angles, must be uploaded to AWG
        if angle == 90:
            # special because the cw phase pulses go in mult of 20 deg
            k.gate('ry90', [q0])
        else:
            k.gate('cw_{:02}'.format(cw_idx), [q0])
        k.measure(q0)
        k.measure(q1)
        # Implements a barrier to align timings
        # k.gate('wait', [q0, q1], 0)
        # hardcoded barrier because of openQL #104
        k.gate('wait', [2, 0], 0)

    p.add_kernel(k)

    if add_cal_points:
        p.add_two_q_cal_points(q0=q0, q1=q1)
    p.compile()

    if add_cal_points:
        cal_pts_idx = [361, 362, 363, 364]
    else:
        cal_pts_idx = []

    p.sweep_points = np.concatenate([angles, cal_pts_idx])
    return p


def two_qubit_state_tomography(
        qubit_idxs,
        bell_state,
        product_state,
        platf_cfg,
        wait_after_flux: float = None,
        flux_codeword: str = 'cz'
) -> OqlProgram:
    p = OqlProgram("state_tomography_2Q_{}_{}_{}".format(product_state, qubit_idxs[0], qubit_idxs[1]), platf_cfg)

    q0 = qubit_idxs[0]
    q1 = qubit_idxs[1]

    calibration_points = ['00', '01', '10', '11']
    measurement_pre_rotations = ['II', 'IF', 'FI', 'FF']
    bases = ['X', 'Y', 'Z']

    ## Explain this ?
    bases_comb = [basis_0 + basis_1 for basis_0 in bases for basis_1 in bases]
    combinations = []
    combinations += [b + '-' + c for b in bases_comb for c in measurement_pre_rotations]
    combinations += calibration_points

    state_strings = ['0', '1', '+', '-', 'i', 'j']
    state_gate = ['i', 'rx180', 'ry90', 'rym90', 'rxm90', 'rx90']
    product_gate = ['0', '0', '0', '0']

    for basis in bases_comb:
        for pre_rot in measurement_pre_rotations:  # tomographic pre-rotation
            k = p.create_kernel('TFD_{}-basis_{}'.format(basis, pre_rot))
            for q_idx in qubit_idxs:
                k.prepz(q_idx)

            # Choose a bell state and set the corresponding preparation pulses
            if bell_state is not None:
                #
                # Q1 |0> --- P1 --o-- A1 -- R1 -- M
                #                 |
                # Q0 |0> --- P0 --o-- I  -- R0 -- M

                if bell_state == 0:  # |Phi_m>=|00>-|11>
                    prep_pulse_q0, prep_pulse_q1 = 'ry90', 'ry90'
                elif bell_state % 10 == 1:  # |Phi_p>=|00>+|11>
                    prep_pulse_q0, prep_pulse_q1 = 'rym90', 'ry90'
                elif bell_state % 10 == 2:  # |Psi_m>=|01>-|10>
                    prep_pulse_q0, prep_pulse_q1 = 'ry90', 'rym90'
                elif bell_state % 10 == 3:  # |Psi_p>=|01>+|10>
                    prep_pulse_q0, prep_pulse_q1 = 'rym90', 'rym90'
                else:
                    raise ValueError('Bell state {} is not defined.'.format(bell_state))

                # Recovery pulse is the same for all Bell states
                after_pulse_q1 = 'rym90'
                k.gate(prep_pulse_q0, [q0])
                k.gate(prep_pulse_q1, [q1])
                k.barrier([])
                # k.gate('cz', [q0, q1])
                k.gate(flux_codeword, [q0, q1])
                k.barrier([])
                # after-rotations
                k.gate(after_pulse_q1, [q1])
                # possibly wait
                if wait_after_flux is not None:
                    k.gate("wait", [q0, q1], round(wait_after_flux * 1e9))
                k.barrier([])

            if product_state is not None:
                for i, string in enumerate(product_state):
                    product_gate[i] = state_gate[state_strings.index(string)]
                k.gate(product_gate[0], [q0])
                k.gate(product_gate[1], [q1])
                k.barrier([])

            if (product_state is not None) and (bell_state is not None):
                raise ValueError(
                    'Confusing requirements, both state {} and bell-state {}'.format(product_state, bell_state))

            # tomographic pre-rotations
            for rot_idx in range(2):
                q_idx = qubit_idxs[rot_idx]
                flip = pre_rot[rot_idx]
                qubit_basis = basis[rot_idx]
                # Basis rotations take the operator Z onto (Ri* Z Ri):
                #              Z     -Z       X       -X       -Y       Y
                # FLIPS        I      F       I        F        I       F
                # BASIS        Z      Z       X        X        Y       Y
                # tomo_gates = ['i', 'rx180', 'ry90', 'rym90', 'rx90', 'rxm90']
                prerot_Z = 'i'
                prerot_mZ = 'rx180'
                prerot_X = 'rym90'
                prerot_mX = 'ry90'
                prerot_Y = 'rx90'
                prerot_mY = 'rxm90'

                if flip == 'I' and qubit_basis == 'Z':
                    k.gate(prerot_Z, [q_idx])
                elif flip == 'F' and qubit_basis == 'Z':
                    k.gate(prerot_mZ, [q_idx])
                elif flip == 'I' and qubit_basis == 'X':
                    k.gate(prerot_X, [q_idx])
                elif flip == 'F' and qubit_basis == 'X':
                    k.gate(prerot_mX, [q_idx])
                elif flip == 'I' and qubit_basis == 'Y':
                    k.gate(prerot_Y, [q_idx])
                elif flip == 'F' and qubit_basis == 'Y':
                    k.gate(prerot_mY, [q_idx])
                else:
                    raise ValueError("flip {} and basis {} not understood".format(flip, basis))
                    k.gate('i', [q_idx])
            k.barrier([])
            for q_idx in qubit_idxs:
                k.measure(q_idx)
            k.barrier([])
            p.add_kernel(k)

    for cal_pt in calibration_points:
        k = p.create_kernel('Cal_{}'.format(cal_pt))
        for q_idx in qubit_idxs:
            k.prepz(q_idx)
        k.barrier([])
        for cal_idx, state in enumerate(cal_pt):
            q_idx = qubit_idxs[cal_idx]
            if state == '1':
                k.gate('rx180', [q_idx])
        k.barrier([])  # barrier guarantees allignment
        for q_idx in qubit_idxs:
            k.measure(q_idx)
        k.barrier([])
        p.add_kernel(k)

    p.compile()
    p.combinations = combinations  # FIXME: violates class definition, pass separately?
    return p


def multi_qubit_Depletion(qubits: list, platf_cfg: str, time: float) -> OqlProgram:
    """

    Performs a measurement pulse and wait time followed by a simultaneous ALLXY on the
    specified qubits:

    |q0> - RO <--wait--> P0 - P1 - RO
    |q1> - RO <--time--> P0 - P1 - RO
     .
     .
     .

     args:
        qubits : List of qubits numbers.
        time   : wait time (s) after readout pulse.
    """

    p = OqlProgram('multi_qubit_Depletion', platf_cfg)

    pulse_combinations = [['i', 'i'], ['rx180', 'rx180'], ['ry180', 'ry180'],
                          ['rx180', 'ry180'], ['ry180', 'rx180'],
                          ['rx90', 'i'], ['ry90', 'i'], ['rx90', 'ry90'],
                          ['ry90', 'rx90'], ['rx90', 'ry180'],
                          ['ry90', 'rx180'],
                          ['rx180', 'ry90'], ['ry180', 'rx90'],
                          ['rx90', 'rx180'],
                          ['rx180', 'rx90'], ['ry90', 'ry180'],
                          ['ry180', 'ry90'],
                          ['rx180', 'i'], ['ry180', 'i'], ['rx90', 'rx90'],
                          ['ry90', 'ry90']]

    for i, pulse_comb in enumerate(pulse_combinations):
        for j in range(2):  # double points
            k = p.create_kernel('Depletion_{}_{}'.format(j, i))
            for qubit in qubits:
                k.prepz(qubit)
                k.measure(qubit)

            wait_nanoseconds = int(round(time / 1e-9))
            for qubit in qubits:
                k.gate("wait", [qubit], wait_nanoseconds)

            if sequence_type == 'simultaneous':  # FIXME: unresolved
                for qubit in qubits:
                    k.gate(pulse_comb[0], [qubit])
                    k.gate(pulse_comb[1], [qubit])
                    k.measure(qubit)

            p.add_kernel(k)

    p.compile()
    return p


def two_qubit_Depletion(
        q0: int, q1: int,
        platf_cfg: str,
        time: float,
        sequence_type='sequential',
        double_points: bool = False
) -> OqlProgram:
    """

    """
    p = OqlProgram('two_qubit_Depletion', platf_cfg)

    pulse_combinations = [['i', 'i'], ['rx180', 'rx180'], ['ry180', 'ry180'],
                          ['rx180', 'ry180'], ['ry180', 'rx180'],
                          ['rx90', 'i'], ['ry90', 'i'], ['rx90', 'ry90'],
                          ['ry90', 'rx90'], ['rx90', 'ry180'],
                          ['ry90', 'rx180'],
                          ['rx180', 'ry90'], ['ry180', 'rx90'],
                          ['rx90', 'rx180'],
                          ['rx180', 'rx90'], ['ry90', 'ry180'],
                          ['ry180', 'ry90'],
                          ['rx180', 'i'], ['ry180', 'i'], ['rx90', 'rx90'],
                          ['ry90', 'ry90']]

    pulse_combinations_tiled = pulse_combinations + pulse_combinations
    if double_points:
        pulse_combinations = [val for val in pulse_combinations
                              for _ in (0, 1)]

    pulse_combinations_q0 = pulse_combinations
    pulse_combinations_q1 = pulse_combinations_tiled

    i = 0
    for pulse_comb_q0, pulse_comb_q1 in zip(pulse_combinations_q0,
                                            pulse_combinations_q1):
        i += 1
        k = p.create_kernel('AllXY_{}'.format(i))
        k.prepz(q0)
        k.prepz(q1)
        k.measure(q0)
        k.measure(q1)

        wait_nanoseconds = int(round(time / 1e-9))
        k.gate("wait", [q0], wait_nanoseconds)
        k.gate("wait", [q1], wait_nanoseconds)
        # N.B. The identity gates are there to ensure proper timing
        if sequence_type == 'interleaved':
            k.gate(pulse_comb_q0[0], [q0])
            k.gate('i', [q1])

            k.gate('i', [q0])
            k.gate(pulse_comb_q1[0], [q1])

            k.gate(pulse_comb_q0[1], [q0])
            k.gate('i', [q1])

            k.gate('i', [q0])
            k.gate(pulse_comb_q1[1], [q1])

        elif sequence_type == 'sandwiched':
            k.gate('i', [q0])
            k.gate(pulse_comb_q1[0], [q1])

            k.gate(pulse_comb_q0[0], [q0])
            k.gate('i', [q1])
            k.gate(pulse_comb_q0[1], [q0])
            k.gate('i', [q1])

            k.gate('i', [q0])
            k.gate(pulse_comb_q1[1], [q1])

        elif sequence_type == 'sequential':
            k.gate(pulse_comb_q0[0], [q0])
            k.gate('i', [q1])
            k.gate(pulse_comb_q0[1], [q0])
            k.gate('i', [q1])
            k.gate('i', [q0])
            k.gate(pulse_comb_q1[0], [q1])
            k.gate('i', [q0])
            k.gate(pulse_comb_q1[1], [q1])

        elif sequence_type == 'simultaneous':
            k.gate(pulse_comb_q0[0], [q0])
            k.gate(pulse_comb_q1[0], [q1])
            k.gate(pulse_comb_q0[1], [q0])
            k.gate(pulse_comb_q1[1], [q1])
        else:
            raise ValueError("sequence_type {} ".format(sequence_type) +
                             "['interleaved', 'simultaneous', " +
                             "'sequential', 'sandwiched']")
        k.measure(q0)
        k.measure(q1)
        p.add_kernel(k)

    p.compile()
    return p


def Two_qubit_RTE(
        QX: int,
        QZ: int,
        platf_cfg: str,
        measurements: int,
        net='i',
        start_states: list = ['0'],
        ramsey_time_1: int = 120,
        ramsey_time_2: int = 120,
        echo: bool = False
) -> OqlProgram:
    """

    """
    p = OqlProgram('RTE', platf_cfg)

    for state in start_states:
        k = p.create_kernel('RTE start state {}'.format(state))
        k.prepz(QX)
        k.prepz(QZ)
        if state == '1':
            k.gate('rx180', [QX])
            k.gate('rx180', [QZ])
        k.gate('wait', [QX, QZ], 0)
        ######################
        # Parity check
        ######################
        for m in range(measurements):
            # Superposition
            k.gate('rx90', [QX])
            k.gate('i', [QZ])
            # CZ emulation
            if echo:
                k.gate('wait', [QX, QZ], int((ramsey_time_1 - 20) / 2))
                k.gate('rx180', [QX])
                k.gate('i', [QZ])
                k.gate('wait', [QX, QZ], int((ramsey_time_1 - 20) / 2))
            else:
                k.gate('wait', [QX, QZ], ramsey_time_1)
            # intermidate sequential
            if net == 'pi' or echo:
                k.gate('rx90', [QX])
            else:
                k.gate('rxm90', [QX])
            k.gate('i', [QZ])
            k.gate('i', [QX])
            k.gate('rx90', [QZ])
            # CZ emulation
            if echo:
                k.gate('wait', [QX, QZ], int((ramsey_time_2 - 20) / 2))
                k.gate('rx180', [QZ])
                k.gate('i', [QX])
                k.gate('wait', [QX, QZ], int((ramsey_time_2 - 20) / 2))
            else:
                k.gate('wait', [QX, QZ], ramsey_time_2)
            # Recovery pulse
            k.gate('i', [QX])
            if net == 'pi' or echo:
                k.gate('rx90', [QZ])
            else:
                k.gate('rxm90', [QZ])
            k.barrier([QX, QZ])
            # Measurement
            k.measure(QX)
            k.measure(QZ)

        p.add_kernel(k)

    p.compile()
    return p


def Two_qubit_RTE_pipelined(
        QX: int,
        QZ: int,
        QZ_d: int,
        platf_cfg: str,
        measurements: int,
        start_states: list = ['0'],
        ramsey_time: int = 120,
        echo: bool = False
) -> OqlProgram:
    """

    """
    p = OqlProgram('RTE_pipelined', platf_cfg)

    for state in start_states:
        k = p.create_kernel('RTE pip start state {}'.format(state))
        k.prepz(QX)
        k.prepz(QZ)
        if state == '1':
            k.gate('rx180', [QX])
            k.gate('rx180', [QZ])
        k.barrier([QX, QZ, QZ_d])
        # k.gate('wait', [QX], 0)
        ######################
        # Parity check
        #####################
        for m in range(measurements):

            k.measure(QZ_d)
            if echo is True:
                k.gate('wait', [QZ_d], ramsey_time + 60)
            else:
                k.gate('wait', [QZ_d], ramsey_time + 40)

            k.gate('rx90', [QZ])
            if echo is True:
                k.gate('wait', [QZ], ramsey_time / 2)
                k.gate('rx180', [QZ])
                k.gate('wait', [QZ], ramsey_time / 2)
                k.gate('rx90', [QZ])
            else:
                k.gate('wait', [QZ], ramsey_time)
                k.gate('rxm90', [QZ])
            k.gate('wait', [QZ], 500)

            k.measure(QX)
            k.gate('rx90', [QX])
            if echo is True:
                k.gate('wait', [QX], ramsey_time / 2)
                k.gate('rx180', [QX])
                k.gate('wait', [QX], ramsey_time / 2)
                k.gate('rx90', [QX])
            else:
                k.gate('wait', [QX], ramsey_time)
                k.gate('rxm90', [QX])

            k.barrier([QX, QZ, QZ_d])

        p.add_kernel(k)

    p.compile()
    return p


def Ramsey_cross(
        wait_time: int,
        angles: list,
        q_rams: int,
        q_meas: int,
        echo: bool,
        platf_cfg: str,
        initial_state: str = '0'
) -> OqlProgram:
    """
    q_target is ramseyed
    q_spec is measured

    """
    p = OqlProgram("Ramsey_msmt_induced_dephasing", platf_cfg)  # FIXME: duplicate name, does not match function name

    for i, angle in enumerate(angles[:-4]):
        cw_idx = angle // 20 + 9
        k = p.create_kernel("Ramsey_azi_" + str(angle))

        k.prepz(q_rams)
        k.prepz(q_meas)
        k.barrier([])

        k.gate('rx90', [q_rams])
        # k.barrier([])
        k.measure(q_rams)
        if echo:
            k.gate("wait", [q_rams], round(wait_time / 2) - 20)
            k.gate('rx180', [q_rams])
            k.gate("wait", [q_rams], round(wait_time / 2))
        else:
            k.gate("wait", [q_rams], wait_time - 20)
        if angle == 90:
            k.gate('ry90', [q_rams])
        elif angle == 0:
            k.gate('rx90', [q_rams])
        else:
            k.gate('cw_{:02}'.format(cw_idx), [q_rams])

        # k.measure(q_rams)
        if initial_state == '1':
            k.gate('rx180', [q_meas])
        k.measure(q_meas)
        if echo:
            k.gate("wait", [q_meas], wait_time + 20)
        else:
            k.gate("wait", [q_meas], wait_time)

        k.barrier([])

        p.add_kernel(k)

    # adding the calibration points
    p.add_single_qubit_cal_points(qubit_idx=q_rams)

    p.compile()
    return p


def TEST_RTE(QX: int, QZ: int, platf_cfg: str, measurements: int) -> OqlProgram:
    """

    """
    p = OqlProgram('Multi_RTE', platf_cfg)

    k = p.create_kernel('Multi_RTE')
    k.prepz(QX)
    k.prepz(QZ)
    ######################
    # Parity check
    ######################
    for m in range(measurements):
        # Superposition
        k.gate('ry90', [QX])
        k.gate('i', [QZ])
        # CZ emulation
        k.gate('i', [QZ, QX])
        k.gate('i', [QZ, QX])
        k.gate('i', [QZ, QX])
        # CZ emulation
        k.gate('i', [QZ, QX])
        k.gate('i', [QZ, QX])
        k.gate('i', [QZ, QX])
        # intermidate sequential
        k.gate('rym90', [QX])
        k.gate('i', [QZ])
        k.gate('i', [QX])
        k.gate('ry90', [QZ])
        # CZ emulation
        k.gate('i', [QZ, QX])
        k.gate('i', [QZ, QX])
        k.gate('i', [QZ, QX])
        # CZ emulation
        k.gate('i', [QZ, QX])
        k.gate('i', [QZ, QX])
        k.gate('i', [QZ, QX])
        # Recovery pulse
        k.gate('i', [QX])
        k.gate('rym90', [QZ])
        # Measurement
        k.measure(QX)
        k.measure(QZ)

    p.add_kernel(k)

    p.compile()
    return p


def multi_qubit_AllXY(qubits_idx: list, platf_cfg: str, double_points: bool = True) -> OqlProgram:
    """
    Used for AllXY measurement and calibration for multiple qubits simultaneously.
    args:

    qubits_idx:     list of qubit indeces
    qubits:         list of qubit names
    platf_cfg:
    double_points:  measure each gate combination twice
    analyze:

    """

    p = OqlProgram("Multi_qubit_AllXY", platf_cfg)

    allXY = [['i', 'i'], ['rx180', 'rx180'], ['ry180', 'ry180'],
             ['rx180', 'ry180'], ['ry180', 'rx180'],
             ['rx90', 'i'], ['ry90', 'i'], ['rx90', 'ry90'],
             ['ry90', 'rx90'], ['rx90', 'ry180'], ['ry90', 'rx180'],
             ['rx180', 'ry90'], ['ry180', 'rx90'], ['rx90', 'rx180'],
             ['rx180', 'rx90'], ['ry90', 'ry180'], ['ry180', 'ry90'],
             ['rx180', 'i'], ['ry180', 'i'], ['rx90', 'rx90'],
             ['ry90', 'ry90']]

    # this should be implicit
    if 0:  # FIXME: p.set_sweep_points has been replaced by p.sweep_points, since that was missing here they are probably not necessary for this function
        p.set_sweep_points(np.arange(len(allXY), dtype=float))

    for i, xy in enumerate(allXY):
        if double_points:
            js = 2
        else:
            js = 1
        for j in range(js):
            k = p.create_kernel("AllXY_{}_{}".format(i, j))
            for qubit in qubits_idx:
                k.prepz(qubit)
                k.gate(xy[0], [qubit])
                k.gate(xy[1], [qubit])
                k.measure(qubit)
            p.add_kernel(k)

    p.compile()
    return p


# FIXME: indentation is wrong in functions below
def multi_qubit_rabi(qubits_idx: list, platf_cfg: str = None) -> OqlProgram:
    p = OqlProgram("Multi_qubit_rabi", platf_cfg)
    k = p.create_kernel("rabi")
    for qubit in qubits_idx:
        k.prepz(qubit)
        k.gate('rx180', [qubit])
        k.measure(qubit)
    p.add_kernel(k)
    p.compile()
    return p


def multi_qubit_ramsey(times, qubits_idx: list, platf_cfg: str) -> OqlProgram:
    n_qubits = len(qubits_idx)
    points = len(times[0])
    p = OqlProgram('Multi_qubit_Ramsey', platf_cfg)

    for i in range(points - 4):
        k = p.create_kernel('Ramsey{}'.format(i))
        for q, qubit in enumerate(qubits_idx):
            k.prepz(qubit)
            wait_nanoseconds = int(round(times[q][i] / 1e-9))
            k.gate('rx90', [qubit])
            k.gate('wait', [qubit], wait_nanoseconds)
            k.gate('rx90', [qubit])
            k.measure(qubit)
        p.add_kernel(k)

    p.add_multi_q_cal_points(qubits=qubits_idx,
                             combinations=['0' * n_qubits, '0' * n_qubits, '1' * n_qubits, '1' * n_qubits])
    p.compile()
    return p


def multi_qubit_T1(times, qubits_idx: list, platf_cfg: str) -> OqlProgram:
    n_qubits = len(qubits_idx)
    points = len(times[0])

    p = OqlProgram('Multi_qubit_T1_', platf_cfg)

    for i in range(points - 4):
        k = p.create_kernel('T1_{}'.format(i))
        for q, qubit in enumerate(qubits_idx):
            k.prepz(qubit)
            wait_nanoseconds = int(round(times[q][i] / 1e-9))
            k.gate('rx180', [qubit])
            k.gate('wait', [qubit], wait_nanoseconds)
            k.measure(qubit)
        p.add_kernel(k)

    p.add_multi_q_cal_points(qubits=qubits_idx,
                             combinations=['0' * n_qubits, '0' * n_qubits, '1' * n_qubits, '1' * n_qubits])
    p.compile()
    return p


def multi_qubit_Echo(times, qubits_idx: list, platf_cfg: str) -> OqlProgram:
    n_qubits = len(qubits_idx)
    points = len(times[0])

    p = OqlProgram('multi_qubit_echo_', platf_cfg)

    for i in range(points - 4):
        k = p.create_kernel('echo_{}'.format(i))
        for q, qubit in enumerate(qubits_idx):
            k.prepz(qubit)
            wait_nanoseconds = int(round(times[q][i] / 1e-9 / 2))
            k.gate('rx90', [qubit])
            k.gate("wait", [qubit], wait_nanoseconds)
            k.gate('rx180', [qubit])
            k.gate("wait", [qubit], wait_nanoseconds)
            angle = (i * 40) % 360
            cw_idx = angle // 20 + 9
            if angle == 0:
                k.gate('rx90', [qubit])
            else:
                k.gate('cw_{:02}'.format(cw_idx), [qubit])

            k.measure(qubit)
        p.add_kernel(k)

    p.add_multi_q_cal_points(qubits=qubits_idx,
                             combinations=['0' * n_qubits, '0' * n_qubits, '1' * n_qubits, '1' * n_qubits])
    p.compile()
    return p


def multi_qubit_flipping(
        number_of_flips,
        qubits_idx: list,
        platf_cfg: str,
        equator: bool = False,
        cal_points: bool = True,
        ax: str = 'x',
        angle: str = '180'
) -> OqlProgram:

    n_qubits = len(qubits_idx)
    if cal_points:
        nf = number_of_flips[:-4]
    else:
        nf = number_of_flips

    p = OqlProgram('multi_qubit_flipping_', platf_cfg)

    for i, n in enumerate(nf):
        k = p.create_kernel('echo_{}'.format(i))
        for q, qubit in enumerate(qubits_idx):
            k.prepz(qubit)
            if equator:
                if ax == 'y':
                    k.gate('ry90', [qubit])
                else:
                    k.gate('rx90', [qubit])
            for j in range(n):
                if ax == 'y' and angle == '90':
                    k.gate('ry90', [qubit])
                    k.gate('ry90', [qubit])
                elif ax == 'y' and angle == '180':
                    k.y(qubit)
                elif angle == '90':
                    k.gate('rx90', [qubit])
                    k.gate('rx90', [qubit])
                else:
                    k.x(qubit)
            k.measure(qubit)
        p.add_kernel(k)

    combinations = ['0' * n_qubits, '0' * n_qubits, '1' * n_qubits, '1' * n_qubits]
    p.add_multi_q_cal_points(qubits=qubits_idx, combinations=combinations)

    p.compile()
    return p


def multi_qubit_motzoi(qubits_idx: list, platf_cfg: str = None) -> OqlProgram:
    p = OqlProgram("Multi_qubit_Motzoi", platf_cfg)

    k = p.create_kernel("yX")
    for qubit in qubits_idx:
        k.prepz(qubit)
        k.gate('ry90', [qubit])
        k.gate('rx180', [qubit])
        k.measure(qubit)
    p.add_kernel(k)

    k = p.create_kernel("xY")
    for qubit in qubits_idx:
        k.prepz(qubit)
        k.gate('rx90', [qubit])
        k.gate('rY180', [qubit])
        k.measure(qubit)
    p.add_kernel(k)

    p.compile()
    return p


# def Ramsey_tomo(qR: int,
#                 qC: int,
#                 exc_specs: list,
#                 platf_cfg: str):
#     """
#     Performs single qubit tomography on a qubit in the equator.
#     """

#     p = OqlProgram('single_qubit_tomo', platf_cfg)

#     Tomo_bases = ['Z', 'X', 'Y']
#     Tomo_gates = ['I', 'rym90', 'rx90']

#     for i in range(2):
#         for basis, gate in zip(Tomo_bases, Tomo_gates):
#             k = oqh.create_kernel('Tomo_{}_off_{}'.format(basis, i), p)
#             k.prepz(qR)
#             k.prepz(qC)
#             for qS in exc_specs:
#                 k.gate('rx180', [qS])
#             k.gate('ry90', [qR])
#             k.gate('cz', [qR, qC], 60)
#             k.gate('wait', [qR, qC], 0)
#             k.gate(gate, [qR])
#             k.measure(qR)
#             k.measure(qC)

#             p.add_kernel(k)

#             k = oqh.create_kernel('Tomo_{}_on_{}'.format(basis, i), p)
#             k.prepz(qR)
#             k.prepz(qC)
#             for qS in exc_specs:
#                 k.gate('rx180', [qS])
#             k.gate('ry90', [qR])
#             k.gate('ry180', [qC])
#             k.gate('cz', [qR, qC], 60)
#             k.gate('wait', [qR, qC], 0)
#             k.gate(gate, [qR])
#             k.gate('ry180', [qC])
#             k.measure(qR)
#             k.measure(qC)

#             p.add_kernel(k)

#     oqh.add_multi_q_cal_points(p,
#                                qubits=[qR, qC],
#                                combinations=['00', '10', '20', '01'])

#     p.compile()
#     return p


def Ramsey_tomo(
        qR: list,
        qC: list,
        exc_specs: list,
        platf_cfg: str,
        flux_codeword: str = 'cz'
) -> OqlProgram:
    """
    Performs single qubit tomography on a qubit in the equator.
    """

    p = OqlProgram('single_qubit_tomo', platf_cfg)

    Tomo_bases = ['Z', 'X', 'Y']
    Tomo_gates = ['I', 'rym90', 'rx90']

    for i in range(2):
        for basis, gate in zip(Tomo_bases, Tomo_gates):
            k = p.create_kernel('Tomo_{}_off_{}'.format(basis, i))
            for qr, qc in zip(qR, qC):
                k.prepz(qr)
                k.prepz(qc)
            for qS in exc_specs:
                k.prepz(qS)

            for qr in qR:
                k.gate('ry90', [qr])
            for qS in exc_specs:
                k.gate('rx180', [qS])

            k.barrier([])
            if flux_codeword is 'cz':
                k.gate(flux_codeword, qR + qC)
            else:

                k.gate(flux_codeword, [0])
            k.barrier([])

            for qr, qc in zip(qR, qC):
                k.gate(gate, [qr])
            k.barrier([])

            for qr, qc in zip(qR, qC):
                k.measure(qr)
                k.measure(qc)

            p.add_kernel(k)

            k = p.create_kernel('Tomo_{}_on_{}'.format(basis, i))
            for qr, qc in zip(qR, qC):
                k.prepz(qr)
                k.prepz(qc)
            for qS in exc_specs:
                k.prepz(qS)

            for qr, qc in zip(qR, qC):
                k.gate('ry90', [qr])
                k.gate('ry180', [qc])
            for qS in exc_specs:
                k.gate('rx180', [qS])

            k.barrier([])
            k.gate('cz', qR + qC, 60)
            k.barrier([])

            for qr, qc in zip(qR, qC):
                k.gate(gate, [qr])
                k.gate('ry180', [qc])
            k.barrier([])

            for qr, qc in zip(qR, qC):
                k.measure(qr)
                k.measure(qc)

            p.add_kernel(k)

    p.add_multi_q_cal_points(
        qubits=qR + qC,
        combinations=['0' * len(qR) + '0' * len(qC),
                      '1' * len(qR) + '0' * len(qC),
                      '2' * len(qR) + '0' * len(qC),
                      '0' * len(qR) + '1' * len(qC)])

    p.compile()
    return p
