#!/usr/bin/env python3
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
"""
An example showing how to read a 10k thermistor using automatic calculation of the temperature from the resistor value.
"""
import asyncio
import logging
import sys
import typing
import warnings
from decimal import Decimal

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
    from gpib_ctypes.Gpib import Gpib

    gpib_board = Gpib(name=0)
    gpib_board.config(0x7, True)  # enable wait for SRQs to speed up waiting for state changes
    gpib_board.close()


# This example will log resistance data to the console
async def main():
    """Read the temperature of the thermistor."""
    try:
        async with HP_3478A(connection=gpib_device) as hp3478a:
            await hp3478a.clear()  # flush all buffers
            await asyncio.gather(
                hp3478a.set_function(FunctionType.NTC),  # Set to 2-wire ohm
                hp3478a.set_range(Range.RANGE_30k),  # Set to 30 kOhm range
                hp3478a.set_trigger(TriggerType.INTERNAL),  # Enable free running trigger
                hp3478a.set_autozero(True),  # Enable Autozero
                hp3478a.set_number_of_digits(6),  # Set the resolution to 5.5 digits
                # Optional: Set the GPIB timeout to > 10 PLC (20 ms) if polling without interrupts is used
                # hp3478a.connection.timeout(600),
            )
            # The NTC paramter are the (normalized) Steinhart-hart coefficients.
            # The formula used to calculate the temperature from the resistance is the following:
            # 1/T=a+b*Log(Rt/R25)+c*Log(Rt/R25)**2+d*Log(Rt/R25)**3
            # For more details on determining those values see the examples/thermistor folder
            hp3478a.set_ntc_parameters(
                a=3.35318065e-03,
                b=2.93792361e-04,
                c=4.04412336e-06,
                d=1.88475068e-07,
                rt25=5000,
            )  # Set Steinhart-Hart coefficients

            # Take the measurements until Ctrl+C is pressed
            async for result in hp3478a.read_all():
                logging.getLogger(__name__).info("%s °C", result - Decimal(273.15))

    # Catch errors from the Prologix IP connection
    except (ConnectionError, ConnectionRefusedError):
        logging.getLogger(__name__).exception(
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
