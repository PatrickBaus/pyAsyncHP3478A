#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ##### BEGIN GPL LICENSE BLOCK #####
#
# Copyright (C) 2021 Patrick Baus
# This file is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This file is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this file.  If not, see <http://www.gnu.org/licenses/>.
#
# ##### END GPL LICENSE BLOCK #####

import asyncio
from decimal import Decimal
from enum import Enum, Flag
import re   # Used to test for numerical return values

class TriggerType(Enum):
    INTERNAL = 1
    EXTERNAL = 2
    SINGLE   = 3
    HOLD     = 4
    FAST     = 5

class DisplayType(Enum):
    NORMAL               = 1
    SHOW_TEXT            = 2
    SHOW_TEXT_AND_FREEZE = 3

class FunctionType(Enum):
    DCV     = 1
    ACV     = 2
    OHM     = 3
    OHMF    = 4
    DCI     = 5
    ACI     = 6
    OHM_EXT = 7

class Range(Enum):
    RANGE_30M   = -2
    RANGE_300M  = -1
    RANGE_3     = 0
    RANGE_30    = 1
    RANGE_300   = 2
    RANGE_3k    = 3
    RANGE_30k   = 4
    RANGE_300k  = 5
    RANGE_3MEG  = 6
    RANGE_30MEG = 7
    RANGE_AUTO  = "A"

class FrontRearSwitchPosition(Enum):
    REAR  = 0
    FRONT = 1

class SrqMask(Flag):
    NONE                = 0b0
    DATA_READY          = 0b1
    SYNTAX_ERROR        = 0b100
    HARDWARE_ERROR      = 0b1000
    FRONT_PANEL_SRQ     = 0b10000
    CALIBRATION_FAILURE = 0b100000

class ErrorFlags(Flag):
    NONE                 = 0b0
    CAL_RAM_CHECKSUM     = 0b1
    RAM_FAILURE          = 0b10
    ROM_FAILURE          = 0b100
    AD_SLOPE_CONVERGENCE = 0b1000
    AD_SELFTEST_FAILURE  = 0b10000
    AD_LINK_FAILURE      = 0b100000

class StatusFlags(Flag):
    NONE                     = 0b0
    INTERNAL_TRIGGER_ENABLED = 0b1
    AUTO_RANGE_ENABLED       = 0b10
    AUTO_ZERO_ENABLED        = 0b100
    LINE_FREQUENCY_50_HZ     = 0b1000
    FRONT_SWITCH_ENABLED     = 0b10000
    CAL_RAM_ENABLED          = 0b100000
    EXTERNAL_TRIGGER_ENABLED = 0b1000000

class SerialPollFlags(Flag):
    NONE                  = 0b0
    SRQ_ON_READING        = 0b1
    SRQ_ON_SYNTAX_ERROR   = 0b10
    SRQ_ON_HARDWARE_ERROR = 0b100
    SRQ_ON_SRQ_BUTTON     = 0b1000
    SRQ_ON_CAL_FAILURE    = 0b10000
    SRQ_ON_POWER_ON       = 0b1000000

# Used to test for numerical return values of the read() command
numerical_test_pattern = re.compile(b"^[+-][0-9]+\.[0-9]+[E][+-][0-9]")

class HP_3478A:
    @property
    def connection(self):
        return self.__conn

    def __init__(self, connection):
        self.__conn = connection

    async def get_id(self):
        """
        The HP 3478A does not support an ID request, so we will report a constant for compatibility
        reasons. The method is not async, but again for compatibility reason chose to be.
        """
        return "HP3478A"

    async def connect(self):
        await self.__conn.connect()
        if hasattr(self.__conn, "set_eot"):
            # Used by the Prologix adapters
            await self.__conn.set_eot(False)

        await asyncio.gather(
            # Default display mode
            self.set_display(DisplayType.NORMAL),
            # Default SRQ Mask
            self.set_srq_mask(SrqMask.NONE)
        )

    async def disconnect(self):
        try:
            await self.local()
            # Wait 0.5 seconds for the DMM to finish reading and accepting the local() command
            # The slowest reading rate is 1.9 readings/s
            await asyncio.sleep(0.5)
        except ConnectionError:
            pass
        finally:
            await self.__conn.disconnect()

    async def read(self, length=None):
        if length is None:
            result = (await self.__conn.read())[:-2]    # strip the EOT characters (\r\n)
        else:
          result = await self.__conn.read(len=length)

        match = numerical_test_pattern.match(result)
        if match is not None:
            if match[0] == b"+9.99999E+9":
                raise OverflowError("DMM input overloaded")
            else:
                return Decimal(match[0].decode('ascii'))
        else:
            return result

    async def __query(self, command, length=None):
        await self.write(command)
        return await self.__conn.read(len=length)

    async def set_display(self, value, text=""):
        assert isinstance(value, DisplayType)
        if value == DisplayType.NORMAL:
            # Do not allow text in normal display mode
            await self.write("D{value:d}".format(value=value.value).encode('ascii'))
        else:
            # The text must be terminated by a control character like \r or \n
            await self.write("D{value:d}{text}\n".format(value=value.value, text=text.rstrip()).encode('ascii'))

    async def set_trigger(self, value):
        assert isinstance(value, TriggerType)
        await self.write("T{value:d}".format(value=value.value).encode('ascii'))

    async def write(self, msg):
        # The message must not be terminated by a new line or any other character
        await self.__conn.write(msg)

    async def set_srq_mask(self, value):
        assert isinstance(value, SrqMask)
        await self.write("M{value:02o}".format(value=value.value).encode('ascii'))

    async def get_front_rear_switch_position(self):
        return FrontRearSwitchPosition(int(await self.__query(b"S")))

    async def clear(self):
        """
        Clear serial poll register
        """
        await self.write(b"K")

    async def reset(self):
        """
        Place the device in DCV, autorange, autozero, single trigger, 4.5 digits mode and erase any output stored in
        the buffers.
        """
        await self.write(b"H0")

    async def remote(self):
        await self.__conn.remote_enable(True)

    async def local(self):
        await self.__conn.ibloc()

    async def set_function(self, value):
        assert isinstance(value, FunctionType)
        await self.write("F{value:d}".format(value=value.value).encode('ascii'))

    async def set_autozero(self, enable):
        assert isinstance(enable, bool)
        await self.write("Z{value:d}".format(value=enable).encode('ascii'))

    async def set_number_of_digits(self, value):
        assert (4 <= value <= 6)
        await self.write("N{value:d}".format(value=value-1).encode('ascii'))

    async def get_error_register(self):
        result = int(await self.__query(b"E"), base=8)    # Convert the octal result to int
        return ErrorFlags(result)

    async def set_range(self, value):
        assert isinstance(value, Range)
        await self.write("R{value}".format(value=value.value).encode('ascii'))

    def __calculate_range(self, function, range_value):
        # The range Enum is basically the exponent of the range
        # Unfortunately the returned bits depend on the function, so we need to add or subtract according to the
        # DMM function
        if function == FunctionType.DCV:
            return Range(range_value - 3)
        elif function == FunctionType.ACV:
            return Range(range_value - 2)
        elif function in (FunctionType.OHM, FunctionType.OHMF, FunctionType.OHM_EXT):
            return Range(range_value + 1)
        elif function in (FunctionType.DCI, FunctionType.ACI):
            return Range(range_value - 2)

    async def get_cal_ram(self):
        result = bytearray()
        for addr in range(256):
            result.append(ord(await self.__query(command=bytes([ord('W'), addr]), length=1)))
        return bytes(result)

    async def set_cal_ram(self, data):
        for addr, data_block in enumerate(data):
            await self.write(bytes([ord('X'), addr, data_block]))

    async def get_status(self):
        # The "B" command is special. It does not contain a line terminator, the
        # device will output exactly 5 bytes and no more. So we need to read exactly
        # 5 bytes.
        result = await self.__query(command=b"B", length=5)
        function = FunctionType((result[0] >> 5) & 0b111)
        dmm_range = self.__calculate_range(function, (result[0] >> 2) & 0b111)
        ndigits = 6 - (result[0] & 0b11)
        status = StatusFlags(result[1])
        srq_flags = SerialPollFlags(result[2])
        error_flags = ErrorFlags(result[3])
        dac_value = result[4]
        return {
            "function": function,
            "range": dmm_range,
            "ndigits": ndigits,
            "status": status,
            "srq_flags": srq_flags,
            "error_flags": error_flags,
            "dac_value": dac_value
        }

    async def serial_poll(self):
        return SerialPollFlags(int(await self.__conn.serial_poll()))

