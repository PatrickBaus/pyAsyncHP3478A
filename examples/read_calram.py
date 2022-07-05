#!/usr/bin/env python3
# pylint: disable=duplicate-code
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
"""This example shows how to pull the calibration memory from the HP 3478A"""
import asyncio
import logging
import sys
import typing
import warnings

import aiofiles

# Devices
from hp3478a_async import HP_3478A
from hp3478a_async.hp_3478a_helper import decode_cal_data, format_cal_string

if typing.TYPE_CHECKING:
    from async_gpib import AsyncGpib
    from prologix_gpib_async import AsyncPrologixGpibEthernetController, EosMode
else:
    # Uncomment if using a Prologix GPIB Ethernet adapter
    from prologix_gpib_async import AsyncPrologixGpibEthernetController, EosMode

    # Uncomment if using linux-gpib
    # from async_gpib import AsyncGpib

# Create the gpib device. We need a timeout of > 10 PLC (20 ms), because the DMM might reply to a conversion request
# and unable to reply to a status request during conversion (maximum time 10 PLC)

if "prologix_gpib_async" in sys.modules:
    IP_ADDRESS = "127.0.0.1"
    # pylint: disable=used-before-assignment  # false positive
    gpib_device = AsyncPrologixGpibEthernetController(IP_ADDRESS, pad=27, timeout=1000, eos_mode=EosMode.APPEND_NONE)

if "async_gpib" in sys.modules:
    # Set the timeout to 1 second (T1s=11)
    # NI GPIB adapter
    gpib_device = AsyncGpib(name=0, pad=27, timeout=11)  # pylint: disable=used-before-assignment  # false positive

# This example will read the calibration memory and write it to a file named 'calram.bin'
async def main():
    """Read the calibration memory from the DMM"""
    async with HP_3478A(connection=gpib_device) as hp3478a:
        await hp3478a.clear()  # flush all buffers
        logging.getLogger(__name__).info("Reading calibration memory. This will take about 10 seconds.")
        result, filehandle = await asyncio.gather(hp3478a.get_cal_ram(), aiofiles.open("calram.bin", mode="x"))
        is_cal_enabled, data = decode_cal_data(result)  # decode to a tuple of dicts
        logging.getLogger(__name__).info("Calibration switch is enabled: %(enabled)s", {"enabled": is_cal_enabled})
        logging.getLogger(__name__).info("Calibration data: %(data)s", {"data": data})
        await filehandle.write(format_cal_string(result))
        await filehandle.close()
        logging.getLogger(__name__).info("Calibration data written to calram.bin")


# Report all mistakes managing asynchronous resources.
warnings.simplefilter("always", ResourceWarning)
logging.basicConfig(
    format="%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s",
    level=logging.INFO,  # Enable logs from the ip connection. Set to debug for even more info
    datefmt="%Y-%m-%d %H:%M:%S",
)

try:
    asyncio.run(main(), debug=False)
except KeyboardInterrupt:
    # The loop will be canceled on a KeyboardInterrupt by the run() method, we just want to suppress the exception
    pass
