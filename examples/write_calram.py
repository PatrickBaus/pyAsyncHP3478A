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
from pyAsyncHP3478A.HP_3478A_helper import decode_cal_data, encode_cal_data

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
        # Read the calram file
        async with aiofiles.open('calram.bin', mode='r') as filehandle:
            result = (await filehandle.read()).replace('\n', '')

        # No need to explicitely bring up the GPIB connection. This will be done by the HP 3478A
        await hp3478a.connect()
        await hp3478a.clear()   # flush all buffers
        is_cal_enabled, data = decode_cal_data(result)   # decode to dict
        data[5]["gain"] = 1.    # Modify entry 5 (Note: This entry is not used, adjust to your liking)
        result = encode_cal_data(data, cal_enable=is_cal_enabled)  # reencode caldata

        await hp3478a.set_cal_ram(result)
        logging.getLogger(__name__).info('Calibration data written to DMM')

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

