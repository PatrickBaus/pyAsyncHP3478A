#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ##### BEGIN GPL LICENSE BLOCK #####
#
# Copyright (C) 2021  Patrick Baus
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# ##### END GPL LICENSE BLOCK #####

import asyncio
import aiofiles
import logging
import warnings
import sys

sys.path.append('..') # Adds main directory to python modules path.

# Devices
from hp3478a_async.hp_3478a import HP_3478A
from hp3478a_async.hp_3478a_helper import format_cal_string, decode_cal_data

# Create the gpib device. We need a timeout of > 10 PLC (20 ms), because the DMM might reply to a conversion request
# and unable to reply to a status request during conversion (maximum time 10 PLC)

# Uncomment if using a Prologix GPIB Ethernet adapter
#from pyAsyncPrologixGpib.pyAsyncPrologixGpib.pyAsyncPrologixGpib import AsyncPrologixGpibEthernetController, EosMode
#from pyAsyncPrologixGpib.pyAsyncPrologixGpib.ip_connection import NotConnectedError, NetworkError
if 'pyAsyncPrologixGpib.pyAsyncPrologixGpib.pyAsyncPrologixGpib' in sys.modules:
    ip_address = '127.0.0.1'
    gpib_device = AsyncPrologixGpibEthernetController(ip_address, pad=27, timeout=1000, eos_mode=EosMode.APPEND_NONE)

# Uncomment if using linux-gpib
from pyAsyncGpib.pyAsyncGpib.AsyncGpib import AsyncGpib
if 'pyAsyncGpib.pyAsyncGpib.AsyncGpib' in sys.modules:
    # Set the timeout to 1 second (T1s=11)
    gpib_device = AsyncGpib(name=0, pad=27, timeout=11)    # NI GPIB adapter

# This example will read the calibration memory and write it to a file named 'calram.bin'
async def main():
    async with HP_3478A(connection=gpib_device) as hp3478a:
        await hp3478a.clear()   # flush all buffers
        logging.getLogger(__name__).info('Reading calibration memory. This will take about 10 seconds.')
        result, filehandle = await asyncio.gather(
            hp3478a.get_cal_ram(),
            aiofiles.open('calram.bin', mode='x')
        )
        is_cal_enabled, data = decode_cal_data(result)   # decode to a list of dicts
        logging.getLogger(__name__).info('Calibration switch is enabled: %(enabled)s', {'enabled': is_cal_enabled})
        logging.getLogger(__name__).info('Calibration data: %(data)s', {'data': data})
        await filehandle.write(format_cal_string(result))
        await filehandle.close()
        logging.getLogger(__name__).info('Calibration data written to calram.bin')

# Report all mistakes managing asynchronous resources.
warnings.simplefilter('always', ResourceWarning)
logging.basicConfig(
    format='%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s',
    level=logging.INFO,    # Enable logs from the ip connection. Set to debug for even more info
    datefmt='%Y-%m-%d %H:%M:%S'
)

try:
    asyncio.run(main(), debug=False)
except KeyboardInterrupt:
    # The loop will be canceled on a KeyboardInterrupt by the run() method, we just want to suppress the exception
    pass

