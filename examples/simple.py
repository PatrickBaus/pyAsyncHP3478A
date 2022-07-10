#!/usr/bin/env python3
# pylint: disable=duplicate-code
"""A simple example showing how to read voltages using the DMM. There is no error handling or logging. See the
other examples for more advanced examples."""
import asyncio

from prologix_gpib_async import AsyncPrologixGpibEthernetController, EosMode

# Devices
from hp3478a_async import HP_3478A, FunctionType, Range, TriggerType

IP_ADDRESS = "127.0.0.1"
gpib_device = AsyncPrologixGpibEthernetController(IP_ADDRESS, pad=27, timeout=10, eos_mode=EosMode.APPEND_NONE)


async def main():
    """This example will print voltages to the console"""
    async with HP_3478A(connection=gpib_device) as hp3478a:
        await hp3478a.clear()  # flush all buffers
        await asyncio.gather(
            hp3478a.set_function(FunctionType.DCV),  # Set to dc voltage
            hp3478a.set_range(Range.RANGE_30),  # Set to 30 V range
            hp3478a.set_trigger(TriggerType.INTERNAL),  # Enable free running trigger
        )

        # Take the measurements until Ctrl+C is pressed
        async for result in hp3478a.read_all():
            print(result)


try:
    asyncio.run(main(), debug=False)
except KeyboardInterrupt:
    # The loop will be canceled on a KeyboardInterrupt by the run() method, we just want to suppress the exception
    pass
