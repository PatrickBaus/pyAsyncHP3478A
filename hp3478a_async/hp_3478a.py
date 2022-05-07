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
"""
This is a asyncIO driver for the HP 3478A DMM to abstract away the GPIB interface.
"""
from __future__ import annotations

import asyncio
from decimal import Decimal
from enum import Enum, Flag
from math import log
import re   # Used to test for numerical return values
from types import TracebackType
from typing import Any, AsyncGenerator, Type
try:
    from typing import Self  # Python 3.11
except ImportError:
    from typing_extensions import Self


class DeviceError(Exception):
    """
    The device returned an error during operation
    """


class DisplayType(Enum):
    """
    The front panel display settings. See page 12 of the manual for details.
    """
    NORMAL = 1
    SHOW_TEXT = 2
    SHOW_TEXT_AND_FREEZE = 3


class FrontRearSwitchPosition(Enum):
    """
    The position of the front/rear binding posts switch on the front panel.
    """
    REAR = 0
    FRONT = 1


class FunctionType(Enum):
    """
    The measurement functions. See page 55 of the extended ohms setting.
    """
    DCV = 1
    ACV = 2
    OHM = 3
    OHMF = 4
    DCI = 5
    ACI = 6
    OHM_EXT = 7
    NTC = 8
    NTCF = 9


class Range(Enum):
    """
    The measurement range of the device. See page 20 of the manual for details.
    """
    RANGE_30M = -2
    RANGE_300M = -1
    RANGE_3 = 0
    RANGE_30 = 1
    RANGE_300 = 2
    RANGE_3k = 3     # small k due to SI pylint: disable=invalid-name
    RANGE_30k = 4     # small k due to SI pylint: disable=invalid-name
    RANGE_300k = 5     # small k due to SI pylint: disable=invalid-name
    RANGE_3MEG = 6
    RANGE_30MEG = 7
    RANGE_AUTO = "A"


class TriggerType(Enum):
    """
    The triggers supported by the DMM. See page 53 of the manual for details.
    """
    INTERNAL = 1
    EXTERNAL = 2
    SINGLE = 3
    HOLD = 4
    FAST = 5


class SrqMask(Flag):
    """
    The service interrupt register flags. See page 47 of the manual for details.
    """
    NONE = 0b0
    DATA_READY = (1 << 0)
    # Bit 1 is always 0
    SYNTAX_ERROR = (1 << 2)
    HARDWARE_ERROR = (1 << 3)
    FRONT_PANEL_SRQ = (1 << 4)
    CALIBRATION_FAILURE = (1 << 5)


class ErrorFlags(Flag):
    """
    The error register flags. See page 62 of the manual for details.
    """
    NONE = 0b0
    CAL_RAM_CHECKSUM = (1 << 0)
    RAM_FAILURE = (1 << 1)
    ROM_FAILURE = (1 << 2)
    AD_SLOPE_CONVERGENCE = (1 << 3)
    AD_SELFTEST_FAILURE = (1 << 4)
    AD_LINK_FAILURE = (1 << 5)


class StatusFlags(Flag):
    """
    The device status register flags. See page 61 of the manual for details.
    """
    NONE = 0b0
    INTERNAL_TRIGGER_ENABLED = (1 << 0)
    AUTO_RANGE_ENABLED = (1 << 1)
    AUTO_ZERO_ENABLED = (1 << 2)
    LINE_FREQUENCY_50_HZ = (1 << 3)
    FRONT_SWITCH_ENABLED = (1 << 4)
    CAL_RAM_ENABLED = (1 << 5)
    EXTERNAL_TRIGGER_ENABLED = (1 << 6)
    # Bit 7 is always zero


class SerialPollFlags(Flag):
    """
    The serial poll flags as returned by SPOLL. See page 50 of the manual for details.
    """
    NONE = 0b0
    SRQ_ON_DATA_READY = (1 << 0)
    # Bit 1 is always 0
    SRQ_ON_SYNTAX_ERROR = (1 << 2)
    SRQ_ON_HARDWARE_ERROR = (1 << 3)
    SRQ_ON_SRQ_BUTTON = (1 << 4)
    SRQ_ON_CAL_FAILURE = (1 << 5)
    SRQ_ON_HAS_SRQ = (1 << 6)
    SRQ_ON_POWER_ON = (1 << 7)


# Used to test for numerical return values of the read() command
numerical_test_pattern = re.compile(rb"^[+-]\d+\.\d+E[+-]\d")


class HP_3478A:     # pylint: disable=too-many-public-methods,invalid-name
    """
    The driver for the HP 3478A 5.5 digit multimeter. It supports both linux-gpib and the Prologix
    GPIB adapters.
    """
    @property
    def connection(self):
        """
        Returns
        ----------
        AsyncGpib or AsyncPrologixGpibController
            The GPIB connection
        """
        return self.__conn

    def __init__(self, connection):
        self.__conn = connection
        self.__special_function: FunctionType | None = None
        # Default constants taken from Amphenol DC95 (Material Type 10kY)
        # https://www.amphenol-sensors.com/hubfs/Documents/AAS-913-318C-Temperature-resistance-curves-071816-web.pdf
        self.__ntc_parameters = {
            'rt25': 10*10**3,
            'a': 3.3540153*10**-3,
            'b': 2.7867185*10**-4,
            'c': 4.0006637*10**-6,
            'd': 1.5575628*10**-7
        }

    async def __aenter__(self) -> Self:
        await self.connect()
        return self

    async def __aexit__(
            self,
            exc_type: Type[BaseException] | None,
            exc: BaseException | None,
            traceback: TracebackType | None
    ) -> None:
        await self.disconnect()

    @staticmethod
    async def get_id() -> str:
        """
        The HP 3478A does not support an ID request, so we will report a constant for compatibility
        reasons. The method is not async, but again for compatibility reasons with other drivers,
        it is declared async.
        """
        return "HP3478A"

    async def connect(self) -> None:
        """
        Connect the GPIB connection and configure the GPIB device for the DMM.
        """
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

    async def disconnect(self) -> None:
        """
        Disconnect the GPIB device and release any lock on the front panel of the device if held.
        """
        try:
            await self.local()
            # Wait 0.5 seconds for the DMM to finish reading and accepting the local() command
            # The slowest reading rate is 1.9 readings/s
            await asyncio.sleep(0.5)
        except ConnectionError:
            pass
        finally:
            await self.__conn.disconnect()

    def set_ntc_parameters(self, a: float, b: float, c: float, d: float, rt25: float):     # pylint: disable=too-many-arguments
        """
        Set the parameters used when in mode `FunctionType.NTC` or
        `FunctionType.NTCF`. The formula for converting resistance values to
        temperature is:
        1/T=a+b*Log(Rt/R25)+c*Log(Rt/R25)**2+d*Log(Rt/R25)**3

        Parameters
        ----------
        a: float
            See formula
        b: float
            See formula
        c: float
            See formula
        d: float
            See formula
        rt25: int
            The resistance at 25 °C
        """
        assert all([rt25 > 0, a > 0, b > 0, c > 0, d > 0])
        self.__ntc_parameters = {
            'a': a,
            'b': b,
            'c': c,
            'd': d,
            'rt25': rt25
        }

    @staticmethod
    def __convert_thermistor_to_temperature(
            value: float,
            a: float,
            b: float,
            c: float,
            d: float,
            rt25: float
    ) -> Decimal | float:     # pylint: disable=too-many-arguments
        """
        Convert a resistance to temperature using the formula
        1/T=a+b*Log(Rt/R25)+c*Log(Rt/R25)**2+d*Log(Rt/R25)**3

        Parameters
        ----------
        value: Decimal or float
            The resistance of the NTC
        a: float
            See formula
        b: float
            See formula
        c: float
            See formula
        d: float
            See formula
        rt25: int
            The resistance at 25 °C

        Returns
        -------
        Decimal or float
            The temperature in K
        """
        return 1 / (a + b * log(value / rt25) + c * log(value / rt25)**2 + d * log(value / rt25)**3)

    def __post_process(self, value: Decimal | float) -> Decimal | float:
        """
        Postprocess the DMM value, if a special function was selected using `set_function()`.
        Returns the unmodified value if no special function was selected.

        Parameters
        ----------
        value: Decimal or float
            The value to postprocess
        Returns
        -------
        Decimal or float
            the postprocessed value
        """
        if self.__special_function is not None:
            try:
                return self.__convert_thermistor_to_temperature(value, **self.__ntc_parameters)
            except ValueError:
                raise ValueError('Cannot convert resistance to temperature. Measurement was: %s.', value) from None
        return value

    async def read(self, length: int | None = None) -> Decimal | bytes:
        """
        Read a single value from the device. If `length' is given, read `length` bytes, else
        read until a line break.

        Parameters
        ----------
        length: int, default=None
            The number of bytes to read. Omit to read a line.

        Returns
        -------
        Decimal or bytes
            Either a value or a number of bytes as defined by `length`.
        """
        if length is None:
            result = (await self.__conn.read())[:-2]    # strip the EOT characters (\r\n)
        else:
            result = await self.__conn.read(length=length)

        match = numerical_test_pattern.match(result)
        if match is not None:
            if match[0] == b"+9.99999E+9":
                raise OverflowError("DMM input overloaded")
            return self.__post_process(Decimal(match[0].decode('ascii')))
        return result   # else return the bytes

    async def read_all(self, length: int | None = None) -> AsyncGenerator[Decimal | bytes, None]:
        """
        Read all values from the device. If `length' is given, read `length` bytes, else
        read until a line break, then yield the result.

        Parameters
        ----------
        length: int, default=None
            The number of bytes to read. Omit to read a line.

        Returns
        -------
        Iterator[Decimal or bytes]
            Either a value or a number of bytes as defined by `length`.
        """
        await self.set_srq_mask(SrqMask.DATA_READY)     # Enable a GPIB interrupt when the conversion is done
        while 'loop not cancelled':
            try:
                status_byte = await self.connection.wait((1 << 11) | (1 << 14))
                if SerialPollFlags.SRQ_ON_DATA_READY in status_byte:
                    result = await self.read(length)
                    yield result
                else:
                    raise DeviceError("Device did not signal ready for read. Status was: %s", status_byte)
            except asyncio.TimeoutError:
                pass

    async def __query(self, command: bytes, length: int | None = None) -> bytes:
        await self.write(command)
        return await self.__conn.read(length=length)

    async def set_display(self, value: DisplayType, text: str = "") -> None:
        """
        Sets a custom display text or display measurands. See page 12 of the manual for details.

        Parameters
        ----------
        value: DisplayType
            The type of text to display on the front panel tft.
        text: str
            The text to display if `value` is not set to DisplayType.NORMAL.
        """
        value = DisplayType(value)
        if value == DisplayType.NORMAL:
            # Do not allow text in normal display mode
            await self.write("D{value:d}".format(value=value.value).encode('ascii'))
        else:
            # The text must be terminated by a control character like \r or \n
            await self.write("D{value:d}{text}\n".format(value=value.value, text=text.rstrip()).encode('ascii'))

    async def set_trigger(self, value: TriggerType) -> None:
        """
        Set the DMM trigger. See page 53 of the manual for details.

        Parameters
        ----------
        value: TriggerType
            The trigger type used when taking measurements.
        """
        value = TriggerType(value)
        await self.write("T{value:d}".format(value=value.value).encode('ascii'))

    async def write(self, msg: bytes) -> None:
        """
        Write data or commands to the instrument. Do not terminate the command with a new line or
        carriage return (\r\n).

        Parameters
        ----------
        msg: bytes
            The string to be sent to the device.
        """
        await self.__conn.write(msg)

    async def set_srq_mask(self, value: SrqMask) -> None:
        """
        Set the service interrupt mask. See page 46 of the manual for details.

        Parameters
        ----------
        value: SrqMask
            The service request register setting.
        """
        value = SrqMask(value)
        await self.write("M{value:02o}".format(value=value.value).encode('ascii'))

    async def get_front_rear_switch_position(self) -> FrontRearSwitchPosition:
        """
        Check whether the front or rear panel binding posts are active.

        Returns
        ----------
        FrontRearSwitchPosition
            The position of the front/rear switch
        """
        return FrontRearSwitchPosition(int(await self.__query(b"S")))

    async def clear(self) -> None:
        """
        Clear serial poll register
        """
        await self.write(b"K")

    async def reset(self) -> None:
        """
        Place the device in DCV, autorange, autozero, single trigger, 4.5 digits mode and erase any output stored in
        the buffers.
        """
        await self.write(b"H0")

    async def local(self) -> None:
        """
        Disable the front panel and allow only GPIB commands.
        """
        await self.__conn.ibloc()

    async def set_function(self, value: FunctionType) -> None:
        """
        Put the device in a certain measurement mode of either DVC, ACV, Ohms, 4-W Ohms, DCI, ACI or
        the extended ohms mode. See page 55 of the manual for details on the extended ohms mode.

        Parameters
        ----------
        value: FunctionType
            The function type to be measured.
        """
        value = FunctionType(value)
        if value in (FunctionType.NTC, FunctionType.NTCF):
            self.__special_function = value
            # Convert to OHM/OHMF
            value = FunctionType(((value.value - 8) % 2) + 3)
        else:
            self.__special_function = None
        await self.write("F{value:d}".format(value=value.value).encode('ascii'))

    async def set_autozero(self, enable: bool) -> None:
        """
        Change the auto-zero mode of the DMM.

        Parameters
        ----------
        enable: bool
            `True` to enable auto-zeroing.
        """
        enable = bool(enable)
        await self.write("Z{value:d}".format(value=enable).encode('ascii'))

    async def set_number_of_digits(self, value: int) -> None:
        """
        Set the number of digits returned by the DMM. This has an influence on the integration time.
        See page 15 of the manual for details.

        Parameters
        ----------
        value: int
            A value between 4 and 6.
        """
        value = int(value)
        assert 4 <= value <= 6
        await self.write("N{value:d}".format(value=value-1).encode('ascii'))

    async def get_error_register(self) -> ErrorFlags:
        """
        Get the contents of the error register. See page 62 of the manual for details.

        Returns
        ----------
        ErrorFlags
            The error register flags
        """
        result = int(await self.__query(b"E"), base=8)    # Convert the octal result to int
        return ErrorFlags(result)

    async def set_range(self, value: Range) -> None:
        """
        Sets the measurement range.

        Parameters
        ----------
        value: Range
            The measurement range.
        """
        value = Range(value)
        await self.write("R{value}".format(value=value.value).encode('ascii'))

    @staticmethod
    def __calculate_range(function: FunctionType, range_value: int) -> Range:
        """
        The range Enum is basically the exponent of the range. Unfortunately the returned bits depend on the function,
        so we need to add or subtract according to the DMM function.
        Parameters
        ----------
        function: FunctionType
            The function that is currently in use
        range_value: int
            The exponent
        Returns
        -------
        Range
            The adjusted range
        """
        range_value_correction = {
            FunctionType.DCV: - 3,
            FunctionType.ACV: -2,
            FunctionType.OHM: 1,
            FunctionType.OHMF: 1,
            FunctionType.OHM_EXT: 1,
            FunctionType.DCI: -2,
            FunctionType.ACI: -2
        }

        return Range(range_value + range_value_correction[function])

    async def get_cal_ram(self) -> bytes:
        """
        Read the internal calibration memory from the NVRAM.

        Returns
        ----------
        bytes
            The contents of the calibration ram.
        """
        result = bytearray()
        for addr in range(256):
            result.append(ord(await self.__query(command=bytes([ord('W'), addr]), length=1)))
        return bytes(result)

    async def set_cal_ram(self, data: bytes) -> None:
        """
        Write to the internal NVRAM. Warning: This can brick the device until a valid calibration
        configuration is written to the NVRAM.

        Parameters
        ----------
        data: bytes
            The data to be written to the calibration memory.
        """
        for addr, data_block in enumerate(data):
            await self.write(bytes([ord('X'), addr, data_block]))

    async def get_status(self) -> dict[str, Any]:
        """
        Read the binary status register of the device. See page 61 of the manual for details.
        """
        # The "B" command is special. It does not contain a line terminator, the
        # device will output exactly 5 bytes and no more. So we need to read exactly
        # 5 bytes.
        result = await self.__query(command=b"B", length=5)
        function = FunctionType((result[0] >> 5) & 0b111)
        if self.__special_function is not None \
                and function is FunctionType(((self.__special_function.value - 8) % 2) + 3):
            # If a special function is enabled in the driver, and the instrument is set to
            # the correct function, we will return the special function instead
            function = self.__special_function
        else:
            # If the correct function is not set on the device, we will disable the special function
            # in the driver
            self.__special_function = None
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

    async def serial_poll(self) -> SerialPollFlags:
        """
        Serial poll the device/GPIB controller.
        """
        return SerialPollFlags(await self.__conn.serial_poll())
