#!/usr/bin/python

import sys

from pycqed.instrument_drivers.physical_instruments.Transport import IPTransport
from pycqed.instrument_drivers.physical_instruments.QuTechCC_core import QuTechCC_core

# parameter handling
ccio = 0
if len(sys.argv)>1:
    ccio = int(sys.argv[1])

val = 0 # 20 ns steps
if len(sys.argv)>2:
    val = int(sys.argv[2])
#    if val>10:
#        val=10

# fixed constants
ip = '192.168.0.241'
reg = 63

cc = QuTechCC_core('cc', IPTransport(ip))
cc.stop()
cc.set_q1_reg(ccio, reg, val)
cc.start()
