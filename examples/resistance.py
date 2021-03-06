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
import logging
import warnings
import sys

sys.path.append("..") # Adds main directory to python modules path.

# Devices
from pyAsyncHP3478A.HP_3478A import HP_3478A, FunctionType, TriggerType, Range, SrqMask

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
    from Gpib import Gpib
    gpib_board = Gpib(name=0)
    gpib_board.config(0x7, True)   # enable wait for SRQs to speed up waiting for state changes
    gpib_board.close()

hp3478a = HP_3478A(connection=gpib_device)

# Uncomment if using linux-gpib
from Gpib import Gpib
from pyAsyncGpib.pyAsyncGpib.AsyncGpib import AsyncGpib
# Set the timeout to 100 seconds (T100s=15)
gpib_device = AsyncGpib(name=0, pad=27, timeout=15)    # NI GPIB adapter

# Create the gpib device. We need a timeout of > 10 PLC (20 ms), because the DMM might reply to a conversion request
# and unable to reply to a status request during conversion (maximum time 10 PLC)
hp3478a = HP_3478A(connection=gpib_device)

# This example will log resistance data to the console
async def main():
    try:
        # No need to explicitly bring up the GPIB connection. This will be done by the instrument.
        await hp3478a.connect()
        await hp3478a.clear()   # flush all buffers
        await asyncio.gather(
            hp3478a.set_srq_mask(SrqMask.DATA_READY),     # Enable a GPIB interrupt when the conversion is done
            hp3478a.set_function(FunctionType.OHMF),      # Set to 4-wire ohm
            hp3478a.set_range(Range.RANGE_30k),           # Set to 30 kOhm range
            hp3478a.set_trigger(TriggerType.INTERNAL),    # Enable free running trigger
            hp3478a.set_autozero(True),                   # Enable Autozero
            hp3478a.set_number_of_digits(6),              # Set the resolution to 5.5 digits
            #hp3478a.connection.timeout(600),              # Optional: Set the GPIB timeout to > 10 PLC (20 ms) if polling without interrupts is used
        )

        # Take the measurements until Ctrl+C is pressed
        while 'loop not canceled':
            # Wait for the SRQ (interupt)
            await hp3478a.connection.wait((1 << 11) | (1<<14))    # Wait for RQS or TIMO
            result = await hp3478a.read()
            logging.getLogger(__name__).info(result)


    # Catch errors from the Prologix IP connection
    #except (ConnectionError, ConnectionRefusedError, NetworkError):
    #    logging.getLogger(__name__).error('Could not connect to remote target. Connection refused. Is the device connected?')
    #except NotConnectedError:
    #    logging.getLogger(__name__).error('Not connected. Did you call .connect()?')
    finally:
        # Disconnect from the instrument. We may safely call disconnect() on a non-connected device, even
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

