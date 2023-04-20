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
"""An example showing how to read resistance values from the DMM."""
import asyncio
import logging
import sys
import typing
import warnings

# Devices
from hp3478a_async import HP_3478A, FunctionType, Range, TriggerType

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
    gpib_device = AsyncPrologixGpibEthernetController(IP_ADDRESS, pad=27, timeout=1, eos_mode=EosMode.APPEND_NONE)

if "async_gpib" in sys.modules:
    # Create the gpib device. We need a timeout of > 10 PLC (20 ms), because the DMM might reply to a conversion request
    # and unable to reply to a status request during conversion (maximum time 10 PLC)
    # Set the timeout to 1 second (T1s=11)
    # NI GPIB adapter
    gpib_device = AsyncGpib(name=0, pad=27, timeout=11)  # pylint: disable=used-before-assignment  # false positive
    try:
        from Gpib import Gpib
    except ImportError:
        from gpib_ctypes.Gpib import Gpib

    gpib_board = Gpib(name=0)
    gpib_board.config(0x7, True)  # enable wait for SRQs to speed up waiting for state changes
    gpib_board.close()


async def main():
    """This example will log resistance data to the console"""
    try:
        async with HP_3478A(connection=gpib_device) as hp3478a:
            await hp3478a.clear()  # flush all buffers
            await asyncio.gather(
                hp3478a.set_function(FunctionType.OHMF),  # Set to 4-wire ohm
                hp3478a.set_range(Range.RANGE_30k),  # Set to 30 kOhm range
                hp3478a.set_trigger(TriggerType.INTERNAL),  # Enable free running trigger
                hp3478a.set_autozero(True),  # Enable Autozero
                hp3478a.set_number_of_digits(6),  # Set the resolution to 5.5 digits
                # Optional: Set the GPIB timeout to > 10 PLC (20 ms) if polling without interrupts is used
                # hp3478a.connection.timeout(600),
            )

            # Take the measurements until Ctrl+C is pressed
            async for result in hp3478a.read_all():
                logging.getLogger(__name__).info(result)

    # Catch errors from the Prologix IP connection
    except (ConnectionError, ConnectionRefusedError):
        logging.getLogger(__name__).error(
            "Could not connect to remote target. Connection refused. Is the device connected?"
        )


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
