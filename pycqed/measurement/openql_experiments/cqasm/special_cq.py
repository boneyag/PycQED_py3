"""
A collection of cQasm routines that do not fit 'single_qubit_cq.py' and 'multi_qubit_cq.py'
FIXME: these files mentioned do not exist yet
"""

from pycqed.measurement.openql_experiments.openql_helpers import OqlProgram


def nested_rus(
        platf_cfg: str,
        ancilla1_idx: int,
        ancilla2_idx: int,
        data_idx: int,
        angle: int = 0,
        echo_period: int = 1860,
        echo_delay_inner_rus: int = 1,
        echo_delay_inner_rus_data: int = 1,
        echo_delay_outer_rus: int = 1
) -> OqlProgram:
    """
    Nested Repeat Until Success experiment

    Args:
        platf_cfg:
        ancilla1_idx:
        ancilla2_idx:
        data_idx:
        angle:
        echo_period:
        echo_delay_inner_rus:
        echo_delay_inner_rus_data:
        echo_delay_outer_rus:

    Returns:
        string containing cQasm source code

    Based on:
        OpenQL test case test_cc.py::test_nested_rus_angle_0
    """

    name = 'nested_rus_angle_{angle}'
    angle_gate = 'cw_{:02}'.format(int(angle) // 20 + 9)    # FIXME: replace cw_* by meaningful name

    src = f"""
        # Note:         file generated by {__file__}::nested_rus
        # File:         {name}.cq
        # Purpose:      test Repeat Until Success

        version 1.2

        pragma @ql.name("{name}")  # set the name of generated files

        .def
        map qAncilla1 = q[{ancilla1_idx}]
        map bAncilla1 = b[{ancilla1_idx}]
        map qAncilla2 = q[{ancilla2_idx}]
        map bAncilla2 = b[{ancilla2_idx}]
        map qData = q[{data_idx}]

        .init
        prepz qAncilla1
        prepz qAncilla2
        prepz qData
        {angle_gate} qData
        barrier

        .rus
        repeat {{
            while (True) {{
                rx2theta qAncilla1
                rym90 qAncilla2
                cz qAncilla1, qAncilla2
                rxm2theta qAncilla1
                ry90beta qAncilla2
                barrier qAncilla1,qAncilla2

                rphi180 qData
                measure_fb qAncilla1
                wait qAncilla2, {echo_delay_inner_rus}
                rphi180 qAncilla2
                wait qAncilla2, {echo_period - echo_delay_inner_rus}
                wait qData, {echo_delay_inner_rus_data}
                barrier qAncilla1,qAncilla2,qData
                if (!bAncilla1) {{
                    break
                }}
        #        barrier qAncilla1,qAncilla2,qData

                rx180 qAncilla1
                rxm90 qAncilla2
                rx180 qData
                barrier qAncilla1,qAncilla2,qData
            }}

            rx180 qAncilla2
            rx180 qData
            rym90 qData
            cz qAncilla2, qData
            ry90 qData

            while(True) {{
                rx2theta qAncilla1
                rym90alpha qAncilla2
                cz qAncilla1, qAncilla2
                rx2thetaalpha qAncilla1
                ry90betapi qAncilla2
                barrier qAncilla1,qAncilla2
                rphi180beta qData
                measure_fb qAncilla1
                wait qAncilla2, {echo_delay_inner_rus}
                rphi180alpha qAncilla2
                wait qAncilla2, {echo_period - echo_delay_inner_rus}
                wait qData, {echo_delay_inner_rus_data}
                barrier qAncilla1,qAncilla2,qData

                if (!bAncilla1) {{
                    break
                }}
        #        barrier qAncilla1,qAncilla2,qData

                rx180 qAncilla1
                rx90alpha qAncilla2
                rx180beta qData
        #        barrier qAncilla1,qAncilla2,qData
            }}

            barrier qAncilla2,qData
            rx180alpha2 qAncilla2
            measure_fb qAncilla2
            wait qData, {echo_delay_outer_rus}
            rphi180beta2 qData
            wait qData, {echo_period - echo_delay_outer_rus}
            barrier qAncilla2,qData
        }} until (!bAncilla2)
        measure_fb qData
    """

    p = OqlProgram(name, platf_cfg)  # NB: name must be identical to name set by "pragma @ql.name" above
    p.compile_cqasm(src)
    return p
