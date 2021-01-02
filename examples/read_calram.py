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
from pyAsyncHP3478A.HP_3478A import HP_3478A
from pyAsyncHP3478A.HP_3478A_helper import format_cal_string, decode_cal_data

from pyAsyncPrologixGpib.pyAsyncPrologixGpib.pyAsyncPrologixGpib import AsyncPrologixGpibEthernetController, EosMode
from pyAsyncPrologixGpib.pyAsyncPrologixGpib.ip_connection import NotConnectedError, ConnectionLostError, NetworkError

ip_address = '127.0.0.1'
#ip_address = '192.168.1.104'

# Create the gpib device. We need a timeout of > 10 PLC (20 ms), because the DMM might reply to a conversion request
# and unable to reply to a status request during conversion (maximum time 10 PLC)
hp3478a = HP_3478A(gpib=AsyncPrologixGpibEthernetController(ip_address, pad=27, timeout=1000, eos_mode=EosMode.APPEND_NONE))

# This example will log resistance data to the console
async def main():
    try: 
        # No need to explicitely bring up the GPIB connection. This will be done by the HP 3478A
        await hp3478a.connect()
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

    except (ConnectionError, ConnectionRefusedError, NetworkError):
        logging.getLogger(__name__).error('Could not connect to remote target. Connection refused. Is the device connected?')
    except NotConnectedError:
        logging.getLogger(__name__).error('Not connected. Did you call .connect()?')
    finally:
        # Disconnect from the HP 3478A. We may safely call diconnect() on a non-connected device, even
        # in case of a connection error
        await hp3478a.disconnect()

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

