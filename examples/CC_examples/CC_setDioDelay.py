#!/usr/bin/python

import sys

from pycqed.instrument_drivers.library.Transport import IPTransport
from pycqed.instrument_drivers.physical_instruments.QuTech.CCCore import CCCore

# parameter handling
ccio = 0
if len(sys.argv)>1:
    ccio = int(sys.argv[1])

val = 0 # 20 ns steps
if len(sys.argv)>2:
    val = int(sys.argv[2])

# fixed constants
ip = '192.168.0.241'

cc = CCCore('cc', IPTransport(ip)) # NB: CCCore loads much quicker then CC
#cc.stop()
cc.set_seqbar_cnt(ccio, val)
#cc.start()
