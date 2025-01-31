"""
Usage:
pytest -v pycqed/tests/openql/test_cqasm.py
pytest -v pycqed/tests/openql/test_cqasm.py --log-level=DEBUG --capture=no
"""

import unittest
import pathlib

#from utils import file_compare

import pycqed.measurement.openql_experiments.generate_CC_cfg_modular as gen
import pycqed.measurement.openql_experiments.cqasm.special_cq as spcq
import pycqed.measurement.openql_experiments.openql_helpers as oqh
from pycqed.measurement.openql_experiments.openql_helpers import OqlProgram


this_path = pathlib.Path(__file__).parent
output_path = pathlib.Path(this_path) / 'test_output_cc'
platf_cfg_path = output_path / 'config_cc_s17_direct_iq_openql_0_10.json'


class Test_cQASM(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        gen.generate_config_modular(platf_cfg_path)
        OqlProgram.output_dir = str(output_path)

    if oqh.is_compatible_openql_version_cc():  # we require unreleased version not yet available for CI
        def test_nested_rus_angle_0(self):
            ancilla1_idx = 10
            ancilla2_idx = 8
            data_idx = 11
            angle = 0

            p = spcq.nested_rus(
                str(platf_cfg_path),
                ancilla1_idx,
                ancilla2_idx,
                data_idx,
                angle
            )

            # check that a file with the expected name has been generated
            assert pathlib.Path(p.filename).is_file()

        @unittest.skip('CC backend cannot yet handle decomposition into if statements')
        def test_parameterized_gate_decomposition(self):
            name = f'test_parametrized_gate_decomp'
            src = f"""
                # Note:         file generated by {__file__}::test_parameterized_gate_decomposition
                # File:         {name}.cq
                # Purpose:      test parameterized gate decomposition

                version 1.2

                pragma @ql.name("{name}")  # set the name of generated files

                _test_rotate q[0],3                
            """

            p = OqlProgram(name, str(platf_cfg_path))  # NB: name must be identical to name set by "pragma @ql.name" above
            p.compile_cqasm(src)

        def test_hierarchical_gate_decomposition(self):
            name = f'test_hierarchical_gate_decomp'
            src = f"""
                # Note:         file generated by {__file__}::test_hierarchical_gate_decomposition
                # File:         {name}.cq
                # Purpose:      test hierarchical gate decomposition

                version 1.2

                pragma @ql.name("{name}")  # set the name of generated files

                _fluxdance_1                
            """

            p = OqlProgram(name, str(platf_cfg_path))  # NB: name must be identical to name set by "pragma @ql.name" above
            p.compile_cqasm(src)

        @unittest.skip("FIXME: disabled")
        def test_experimental_functions(self):
            name = f'test_experimental_functions'
            src = f"""
                # Note:         file generated by {__file__}::test_experimental_functions
                # File:         {name}.cq
                # Purpose:      test experimental functions

                version 1.2

                pragma @ql.name("{name}")  # set the name of generated files

                map i = creg(0)
                map b = breg(0) # FIXME: assign on PL state, not DSM

                # NB: on all CCIO:  
                set i = rnd_seed(0, 12345678)                
                set i = rnd_threshold(0, 0.5)                
                # set b = rnd(0)
                cond (rnd(0)) rx180 q[0]              
            """

            p = OqlProgram(name, str(platf_cfg_path))  # NB: name must be identical to name set by "pragma @ql.name" above
            p.compile_cqasm(src)

        def test_decompose_measure_specialized(self):
            # NB: OpenQL < 0.10.3 reverses order of decompositions
            name = f'test_decompose_measure_specialized'
            src = f"""
                # Note:         file generated by {__file__}::test_decompose_measure_specialized
                # File:         {name}.cq
                # Purpose:      test specialized decomposition of measure

                version 1.2

                pragma @ql.name("{name}")  # set the name of generated files

                measure q[0]  
                measure q[6]  # specialized: prepend with rx12             
            """

            p = OqlProgram(name, str(platf_cfg_path))  # NB: name must be identical to name set by "pragma @ql.name" above
            p.compile_cqasm(src)

        # FIXME: not cqasm, move
        def test_decompose_measure_specialized_api(self):
            p = OqlProgram("test_decompose_measure_specialized_api", str(platf_cfg_path))

            k = p.create_kernel("kernel")
            k.measure(0)
            k.measure(6)
            p.add_kernel(k)
            p.compile()

        # FIXME: not cqasm, move
        @unittest.skip("FIXME: disabled, call does not match prototype")
        def test_decompose_fluxdance_api(self):
            p = OqlProgram("test_decompose_fluxdance_api", str(platf_cfg_path))

            k = p.create_kernel("kernel")
            k.gate("_flux_dance_1", 0)
            p.add_kernel(k)
            p.compile()

        def test_measure_map_output(self):
            name = f'test_measure_map_output'
            src = f"""
                # Note:         file generated by {__file__}::test_measure_map_output
                # File:         {name}.cq
                # Purpose:      test map output file for measurements

                version 1.2

                pragma @ql.name("{name}")  # set the name of generated files

                measure q[0:16]  
                measure q[6]
                barrier
                measure q[0:8]
            """

            p = OqlProgram(name, str(platf_cfg_path))  # NB: name must be identical to name set by "pragma @ql.name" above
            p.compile_cqasm(src)

        def test_qi_barrier(self):
            name = f'test_qi_barrier'
            src = f"""
                # Note:         file generated by {__file__}::test_qi_barrier
                # File:         {name}.cq
                # Purpose:      test qi barrier

                version 1.2

                pragma @ql.name("{name}")  # set the name of generated files

                x q[0]
                barrier q[0,1]
                x q[1]  
            """

            p = OqlProgram(name, str(platf_cfg_path))  # NB: name must be identical to name set by "pragma @ql.name" above
            p.compile_cqasm(src)

        def test_qi_curly_brackets(self):
            name = f'test_qi_curly_brackets'
            src = f"""
                # Note:         file generated by {__file__}::test_qi_curly_brackets
                # File:         {name}.cq
                # Purpose:      test qi curly brackets

                version 1.2

                pragma @ql.name("{name}")  # set the name of generated files

                {{ x q[0,2] }}
            """

            p = OqlProgram(name, str(platf_cfg_path))  # NB: name must be identical to name set by "pragma @ql.name" above
            p.compile_cqasm(src)

        def test_qi_wait(self):
            name = f'test_qi_wait'
            src = f"""
                # Note:         file generated by {__file__}::test_qi_wait
                # File:         {name}.cq
                # Purpose:      test qi wait

                version 1.2

                pragma @ql.name("{name}")  # set the name of generated files

                prepz q[0]
                wait q[0], 100
                measure q[0]
            """

            p = OqlProgram(name, str(platf_cfg_path))  # NB: name must be identical to name set by "pragma @ql.name" above
            p.compile_cqasm(src)


    else:
        @unittest.skip('OpenQL version does not support CC')
        def test_fail(self):
            pass
