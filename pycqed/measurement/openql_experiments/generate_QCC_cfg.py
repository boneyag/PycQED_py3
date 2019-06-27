import json


def generate_config(filename: str,
                    mw_pulse_duration: int = 20,
                    flux_pulse_duration: int=40,
                    ro_duration: int = 800,
                    mw_mw_buffer=0,
                    mw_flux_buffer=0,
                    flux_mw_buffer=0,
                    ro_latency: int = 0,
                    mw_latency: int = 0,
                    fl_latency: int = 0,
                    init_duration: int = 200000):
    """
    Generates a configuration file for OpenQL for use with the CCLight.
    Args:
        filename (str)          : location where to write the config json file
        mw_pulse_duration (int) : duration of the mw_pulses in ns.
            N.B. this should be 20 as the VSM marker is hardcoded to be of that
            length.
        flux_pulse_duration (int) : duration of flux pulses in ns.
        ro_duration       (int) : duration of the readout, including depletion
                                    in ns.
        init_duration     (int) : duration of the initialization/reset
            operation in ns. This corresponds to the wait time before every
            experiment.

    The format for the configuration is a completely flattened file, this means
    that for every operation (including it's target) there is a separate entry
    in the JSON. The details of what can be specified are given in the OpenQL
    documentation under "configuration_specification".
    """

    qubits = ['q0', 'q1', 'q2', 'q3', 'q4', 'q5', 'q6', 'q7', 'q8', 'q9', 'q10',
             'q11', 'q12', 'q13', 'q14', 'q15', 'q16']
    lut_map = ['i {}', 'rx180 {}', 'ry180 {}', 'rx90 {}', 'ry90 {}',
               'rxm90 {}', 'rym90 {}', 'rphi90 {}', 'spec {}', 'rx12 {}',
               'square {}']
    flux_tuples = [("q0", "q2"), ("q2", "q0"),
                   ("q0", "q3"), ("q3", "q0"),
                   ("q1", "q4"), ("q4", "q1"),
                   ("q1", "q5"), ("q5", "q1"),
                   ("q2", "q5"), ("q5", "q2"),
                   ("q2", "q6"), ("q6", "q2"),
                   ("q3", "q6"), ("q6", "q3"),
                   ("q4", "q7"), ("q7", "q4"),
                   ("q5", "q7"), ("q7", "q5"),
                   ("q5", "q8"), ("q8", "q5"),
                   ("q6", "q8"), ("q8", "q6"),
                   ("q6", "q9"), ("q9", "q6"),
                   ("q7", "q10"), ("q10", "q7"),
                   ("q8", "q10"), ("q10", "q8"),
                   ("q8", "q11"), ("q11", "q8"),
                   ("q9", "q11"), ("q11", "q9"),
                   ("q9", "q12"), ("q12", "q9"),
                   ("q10", "q13"), ("q13", "q10"),
                   ("q10", "q14"), ("q14", "q10"),
                   ("q11", "q14"), ("q14", "q11"),
                   ("q11", "q15"), ("q15", "q11"),
                   ("q12", "q15"), ("q15", "q12"),
                   ("q13", "q16"), ("q16", "q13"),
                   ("q14", "q16"), ("q16", "q14")
                   ]

    """ 
    CC_light compiler is still used in QCC, but simply with different number of qubits
    assigned and a different topology definition (flux_tuples)
    """
    cfg = {
        "eqasm_compiler": "cc_light_compiler",
        "hardware_settings": {
            "qubit_number": 17,
            "cycle_time": 20,
            "mw_mw_buffer": mw_mw_buffer,
            "mw_flux_buffer": mw_flux_buffer,
            "mw_readout_buffer": 0,
            "flux_mw_buffer": flux_mw_buffer,
            "flux_flux_buffer": 0,
            "flux_readout_buffer": 0,
            "readout_mw_buffer": 0,
            "readout_flux_buffer": 0,
            "readout_readout_buffer": 0},
        "instructions": {},
        "resources":
            {"qubits": {"count": 17},
             "qwgs": {"count": 3,
                      "connection_map":
                      {
                          "0": [7, 8, 9],
                          "1": [1, 2, 3, 13, 14, 15],
                          "2": [0, 4, 5, 6, 10, 11, 12, 16]
                      }
                      },
             "meas_units": {"count": 17,
                            "connection_map": {"0": [0],
                                               "1": [1],
                                               "2": [2],
                                               "3": [3],
                                               "4": [4],
                                               "5": [5],
                                               "6": [6],
                                               "7": [7],
                                               "8": [8],
                                               "9": [9],
                                               "10": [10],
                                               "11": [11],
                                               "12": [12],
                                               "13": [13],
                                               "14": [14],
                                               "15": [15],
                                               "16": [16]
                                               }
                            },
             # FIXME OpenQL #103
             # "meas_units": {"count": 2,
             #                "connection_map": {"0": [0, 2, 3, 5, 6],
             #                                   "1": [1, 4]}
             #                },
             "edges": {"count": 24,
                       "connection_map": {
                           "0": [],
                           "1": [],
                           "2": [],
                           "3": [],
                           "4": [],
                           "5": [],
                           "6": [],
                           "7": [],
                           "8": [],
                           "9": [],
                           "10": [],
                           "11": [],
                           "12": [],
                           "13": [],
                           "14": [],
                           "15": [],
                           "16": [],
                           "17": [],
                           "18": [],
                           "19": [],
                           "20": [],
                           "21": [],
                           "22": [],
                           "23": []
                       }
                       }
             },
        "topology":
            {
            "x_size": 5,
            "y_size": 3,
            "qubits":
            [
                {"id": 0,  "x": 4, "y": 6},
                {"id": 1,  "x": 1, "y": 5},
                {"id": 2,  "x": 3, "y": 5},
                {"id": 3,  "x": 5, "y": 5},
                {"id": 4,  "x": 0, "y": 4},
                {"id": 5,  "x": 2, "y": 4},
                {"id": 6,  "x": 4, "y": 4},
                {"id": 7,  "x": 1, "y": 3},
                {"id": 8,  "x": 3, "y": 3},
                {"id": 9,  "x": 5, "y": 3},
                {"id": 10,  "x": 2, "y": 2},
                {"id": 11,  "x": 4, "y": 2},
                {"id": 12,  "x": 6, "y": 2},
                {"id": 13,  "x": 1, "y": 1},
                {"id": 14,  "x": 3, "y": 1},
                {"id": 15,  "x": 5, "y": 1},
                {"id": 16,  "x": 2, "y": 0}
            ],
            "edges":
            [
                {"id": 0,  "src": 2, "dst": 0},
                {"id": 1,  "src": 3, "dst": 0},
                {"id": 2,  "src": 4, "dst": 1},
                {"id": 3,  "src": 5, "dst": 1},
                {"id": 4,  "src": 5, "dst": 2},
                {"id": 5,  "src": 6, "dst": 2},
                {"id": 6,  "src": 6, "dst": 3},
                {"id": 7,  "src": 7, "dst": 4},
                {"id": 8,  "src": 7, "dst": 5},
                {"id": 9,  "src": 8, "dst": 5},
                {"id": 10,  "src": 8, "dst": 6},
                {"id": 11,  "src": 9, "dst": 6},
                {"id": 12,  "src": 10, "dst": 7},
                {"id": 13,  "src": 10, "dst": 8},
                {"id": 14,  "src": 11, "dst": 8},
                {"id": 15,  "src": 11, "dst": 9},
                {"id": 16,  "src": 12, "dst": 9},
                {"id": 17,  "src": 13, "dst": 10},
                {"id": 18,  "src": 14, "dst": 10},
                {"id": 19,  "src": 14, "dst": 11},
                {"id": 20,  "src": 15, "dst": 11},
                {"id": 21,  "src": 15, "dst": 12},
                {"id": 22,  "src": 16, "dst": 13},
                {"id": 23,  "src": 16, "dst": 14}
            ]
        },

        "gate_decomposition": {
            "x %0": ["rx180 %0"],
            "y %0": ["ry180 %0"],
            "roty90 %0": ["ry90 %0"],
            "cnot %0,%1": ["ry90 %1", "cz %0,%1", "ry90 %1"],

            # To support other forms of writing the same gates
            "x180 %0": ["rx180 %0"],
            "y180 %0": ["ry180 %0"],
            "y90 %0": ["ry90 %0"],
            "x90 %0": ["rx90 %0"],
            "my90 %0": ["rym90 %0"],
            "mx90 %0": ["rxm90 %0"],

            # Clifford decomposition per Eptstein et al. Phys. Rev. A 89, 062321
            # (2014)
            "cl_0 %0": ['i %0'],
            "cl_1 %0": ['ry90 %0', 'rx90 %0'],
            "cl_2 %0": ['rxm90 %0', 'rym90 %0'],
            "cl_3 %0": ['rx180 %0'],
            "cl_4 %0": ['rym90 %0', 'rxm90 %0'],
            "cl_5 %0": ['rx90 %0', 'rym90 %0'],
            "cl_6 %0": ['ry180 %0'],
            "cl_7 %0": ['rym90 %0', 'rx90 %0'],
            "cl_8 %0": ['rx90 %0', 'ry90 %0'],
            "cl_9 %0": ['rx180 %0', 'ry180 %0'],
            "cl_10 %0": ['ry90 %0', 'rxm90 %0'],
            "cl_11 %0": ['rxm90 %0', 'ry90 %0'],

            "cl_12 %0": ['ry90 %0', 'rx180 %0'],
            "cl_13 %0": ['rxm90 %0'],
            "cl_14 %0": ['rx90 %0', 'rym90 %0', 'rxm90 %0'],
            "cl_15 %0": ['rym90 %0'],
            "cl_16 %0": ['rx90 %0'],
            "cl_17 %0": ['rx90 %0', 'ry90 %0', 'rx90 %0'],
            "cl_18 %0": ['rym90 %0', 'rx180 %0'],
            "cl_19 %0": ['rx90 %0', 'ry180 %0'],
            "cl_20 %0": ['rx90 %0', 'rym90 %0', 'rx90 %0'],
            "cl_21 %0": ['ry90 %0'],
            "cl_22 %0": ['rxm90 %0', 'ry180 %0'],
            "cl_23 %0": ['rx90 %0', 'ry90 %0', 'rxm90 %0']
        },
    }

    for q in qubits:
        cfg["instructions"]["prepz {}".format(q)] = {
            "duration": init_duration,
            "latency": 0,
            "qubits": [q],
            "matrix": [[0.0, 1.0], [1.0, 0.0], [1.0, 0.0], [0.0, 0.0]],
            "disable_optimization": True,
            "type": "none",
            "cc_light_instr_type": "single_qubit_gate",
            "cc_light_instr": "prepz",
            "cc_light_codeword": 0,
            "cc_light_opcode": 2
        }

    for q in qubits:
        cfg["instructions"]["measure {}".format(q)] = {
            "duration": ro_duration,
            "latency": ro_latency,
            "qubits": [q],
            "matrix": [[0.0, 1.0], [1.0, 0.0], [1.0, 0.0], [0.0, 0.0]],
            "disable_optimization": False,
            "type": "readout",
            "cc_light_instr_type": "single_qubit_gate",
            "cc_light_instr": "measz",
            "cc_light_codeword": 0,
            "cc_light_opcode": 4
        }

    for CW in range(len(lut_map)):
        for q in qubits:
            cfg["instructions"][lut_map[CW].format(q)] = {
                "duration": mw_pulse_duration,
                "latency": mw_latency,
                "qubits": [q],
                "matrix": [[0.0, 1.0], [1.0, 0.0], [1.0, 0.0], [0.0, 0.0]],
                "disable_optimization": False,
                "type": "mw",
                "cc_light_instr_type": "single_qubit_gate",
                "cc_light_instr": "cw_{:02}".format(CW),
                "cc_light_codeword": CW,
                "cc_light_opcode": 8+CW}

            cfg["instructions"]['c1'+lut_map[CW].format(q)] = {
                "duration": mw_pulse_duration,
                "latency": mw_latency,
                "qubits": [q],
                "matrix": [[0.0, 1.0], [1.0, 0.0], [1.0, 0.0], [0.0, 0.0]],
                "disable_optimization": False,
                "type": "mw",
                "cc_light_instr_type": "single_qubit_gate",
                "cc_light_instr": "C1_cw_{:02}".format(CW),
                "cc_light_codeword": CW,
                "cc_light_opcode": 32+8+CW,
                "cc_light_cond": 1}  # 1 means : do if last meas. == 1


            cfg["instructions"]['c0'+lut_map[CW].format(q)] = {
                "duration": mw_pulse_duration,
                "latency": mw_latency,
                "qubits": [q],
                "matrix": [[0.0, 1.0], [1.0, 0.0], [1.0, 0.0], [0.0, 0.0]],
                "disable_optimization": False,
                "type": "mw",
                "cc_light_instr_type": "single_qubit_gate",
                "cc_light_instr": "C0_cw_{:02}".format(CW),
                "cc_light_codeword": CW,
                "cc_light_opcode": 32+16+CW,
                "cc_light_cond": 2}  # 2 means : do if last meas. == 0


    for CW in range(32):
        for q in qubits:
            cfg["instructions"]["cw_{:02} {}".format(CW, q)] = {
                "duration": mw_pulse_duration,
                "latency": mw_latency,
                "qubits": [q],
                "matrix": [[0.0, 1.0], [1.0, 0.0], [1.0, 0.0], [0.0, 0.0]],
                "disable_optimization": False,
                "type": "mw",
                "cc_light_instr_type": "single_qubit_gate",
                "cc_light_instr": "cw_{:02}".format(CW),
                "cc_light_codeword": CW,
                "cc_light_opcode": 8+CW}

    for q in qubits:
        cfg["instructions"]["compensate {}".format(q)] = {
            "duration": mw_pulse_duration,
            "latency": mw_latency,
            "qubits": [q],
            "matrix": [[0.0, 1.0], [1.0, 0.0], [1.0, 0.0], [0.0, 0.0]],
            "disable_optimization": False,
            "type": "mw",
            "cc_light_instr_type": "single_qubit_gate",
            "cc_light_instr": "cw_00",
            "cc_light_codeword": 0,
            "cc_light_opcode": 8+0}

    # N.B. The codewords for CZ pulses need to be further specified.
    # I do not expect this to be correct for now.
    for ft in flux_tuples:
        # FIXME add space back in
        cfg["instructions"]["cz {},{}".format(ft[0], ft[1])] = {
            "duration": flux_pulse_duration,
            "latency": fl_latency,
            "qubits": [ft[0], ft[1]],
            "matrix": [[0.0, 1.0], [1.0, 0.0], [1.0, 0.0], [0.0, 0.0]],
            "disable_optimization": True,
            "type": "flux",
            "cc_light_instr_type": "two_qubit_gate",
            "cc_light_instr": "fl_cw_{:02}".format(1),
            "cc_light_right_codeword": 1,
            "cc_light_left_codeword": 1,
            "cc_light_opcode": 128+1
        }

    for cw_flux in range(8):
        for ft in flux_tuples:
            cfg["instructions"]["fl_cw_{:02} {},{}".format(cw_flux,
                                                           ft[0], ft[1])] = {
                "duration": flux_pulse_duration,
                "latency": fl_latency,
                "qubits": [ft[0], ft[1]],
                "matrix": [[0.0, 1.0], [1.0, 0.0], [1.0, 0.0], [0.0, 0.0]],
                "disable_optimization": True,
                "type": "flux",
                "cc_light_instr_type": "two_qubit_gate",
                "cc_light_instr": "fl_cw_{:02}".format(cw_flux),
                "cc_light_right_codeword": cw_flux,
                "cc_light_left_codeword": cw_flux,
                "cc_light_opcode": 128+cw_flux
            }

    with open(filename, 'w') as f:
        json.dump(cfg, f, indent=4)
