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
import re  # Used to test for numerical return values
from dataclasses import dataclass
from decimal import Decimal
from math import log
from types import TracebackType
from typing import TYPE_CHECKING, AsyncGenerator, Type

from hp3478a_async.enums import DisplayType, FrontRearSwitchPosition, FunctionType, Range, TriggerType
from hp3478a_async.errors import DeviceError
from hp3478a_async.flags import ErrorFlags, SerialPollFlags, SrqMask, StatusFlags

try:
    from typing import Self  # type: ignore # Python 3.11
except ImportError:
    from typing_extensions import Self

if TYPE_CHECKING:
    from async_gpib import AsyncGpib
    from prologix_gpib_async import AsyncPrologixGpibController


@dataclass
class DmmStatus:
    """The device status of them DMM"""

    function: FunctionType
    range: Range
    ndigits: int
    status: StatusFlags
    srq_flags: SerialPollFlags
    error_flags: ErrorFlags
    dac_value: int


@dataclass
class NtcParameters:
    """
    The Steinhart-Hart coefficient of an NTC thermistor. The formula to calculate the temperature from the resistance is
    as follows:

    1/T=a+b*Log(Rt/R25)+c*Log(Rt/R25)**2+d*Log(Rt/R25)**3

    See `Wikipedia: Steinhart–Hart equation <https://en.wikipedia.org/wiki/Steinhart%E2%80%93Hart_equation>`_ for more
    details.
    """

    a: float  # pylint: disable=invalid-name  # this is standard naming convention
    b: float  # pylint: disable=invalid-name  # this is standard naming convention
    c: float  # pylint: disable=invalid-name  # this is standard naming convention
    d: float  # pylint: disable=invalid-name  # this is standard naming convention
    rt25: float

    def __post_init__(self):
        assert all([self.rt25 > 0, self.a > 0, self.b > 0, self.c > 0, self.d > 0])


# Used to test for numerical return values of the read() command
numerical_test_pattern = re.compile(rb"^[+-]\d+\.\d+E[+-]\d")


class HP_3478A:  # noqa pylint: disable=too-many-public-methods,invalid-name
    """
    The driver for the HP 3478A 5.5 digit multimeter. It supports both linux-gpib and the Prologix
    GPIB adapters.
    """

    @property
    def connection(self) -> AsyncGpib | AsyncPrologixGpibController:
        """
        The GPIB connection.
        """
        return self.__conn

    def __init__(self, connection: AsyncGpib | AsyncPrologixGpibController) -> None:
        """
        Create an HP 3478A with the GPIB connection given.

        Parameters
        ----------
        connection: AsyncGpib or AsyncPrologixGpibController
            The GPIB connection
        """
        self.__conn = connection
        self.__special_function: FunctionType | None = None
        # Default constants taken from Amphenol DC95 (Material Type 10kY)
        # https://www.amphenol-sensors.com/hubfs/Documents/AAS-913-318C-Temperature-resistance-curves-071816-web.pdf
        self.__ntc_parameters: NtcParameters = NtcParameters(
            rt25=10 * 10**3,
            a=3.3540153 * 10**-3,
            b=2.7867185 * 10**-4,
            c=4.0006637 * 10**-6,
            d=1.5575628 * 10**-7,
        )

    def __str__(self) -> str:
        return f"HEWLETT-PACKARD 3478A at {str(self.connection)}"

    async def __aenter__(self) -> Self:
        await self.connect()
        return self

    async def __aexit__(
        self, exc_type: Type[BaseException] | None, exc: BaseException | None, traceback: TracebackType | None
    ) -> None:
        await self.disconnect()

    @staticmethod
    async def get_id() -> tuple[str, str, str, str]:
        """
        The HP 3478A does not support an ID request, so this function returns the constant
        `"HEWLETT-PACKARD", "3478A", "0", "0"` to emulate the `*IDN?` SCPI command. The method is not async, but for
        compatibility reasons with other drivers, it is declared async.

        Returns
        -------
        tuple of str
            A SCPI compliant id string
        """
        return "HEWLETT-PACKARD", "3478A", "0", "0"

    async def connect(self) -> None:
        """
        Connect the GPIB connection and configure the GPIB device for the DMM. This function must be called from the
        loop and takes care of connecting the GPIB adapter.
        """
        await self.__conn.connect()
        if hasattr(self.__conn, "set_eot"):
            # Used by the Prologix adapters
            await self.__conn.set_eot(False)

        await asyncio.gather(
            # Default display mode
            self.set_display(DisplayType.NORMAL),
            # Default SRQ Mask
            self.set_srq_mask(SrqMask.NONE),
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

    def set_ntc_parameters(
        self, a: float, b: float, c: float, d: float, rt25: float
    ):  # pylint: disable=invalid-name,too-many-arguments  # this is standard naming convention
        """
        Set the parameters used when in mode :attr:`FunctionType.NTC <hp3478a_async.enums.FunctionType.NTC>` or
        :attr:`FunctionType.NTCF <hp3478a_async.enums.FunctionType.NTCF>`. The parameters can be found in the datasheet
        of the thermistor. The formula for converting resistance values to temperature is:

        1/T=a+b*Log(Rt/R25)+c*Log(Rt/R25)**2+d*Log(Rt/R25)**3

        See `Wikipedia: Steinhart–Hart equation <https://en.wikipedia.org/wiki/Steinhart%E2%80%93Hart_equation>`_ for
        more details.

        Parameters
        ----------
        a: float
            The parameters of the NTC thermistor used
        b: float
            The parameters of the NTC thermistor used
        c: float
            The parameters of the NTC thermistor used
        d: float
            The parameters of the NTC thermistor used
        rt25: float
            The resistance of the NTC at 25 °C
        """
        self.__ntc_parameters = NtcParameters(a, b, c, d, rt25)

    @staticmethod
    def __convert_thermistor_to_temperature(value: Decimal, ntc_parameters: NtcParameters) -> Decimal:
        """
        Convert a resistance to temperature using the formula 1/T=a+b*Log(Rt/R25)+c*Log(Rt/R25)**2+d*Log(Rt/R25)**3.

        Parameters
        ----------
        value: Decimal or float
            The resistance of the NTC
        ntc_parameters: NtcParameters

        Returns
        -------
        Decimal or float
            The temperature in K
        """
        # Note: float precision is good enough for thermistors, so we convert the value to float and finally back to
        # Decimal
        return Decimal(
            1
            / (
                ntc_parameters.a
                + ntc_parameters.b * log(float(value) / ntc_parameters.rt25)
                + ntc_parameters.c * log(float(value) / ntc_parameters.rt25) ** 2
                + ntc_parameters.d * log(float(value) / ntc_parameters.rt25) ** 3
            )
        )

    def __post_process(self, value: Decimal) -> Decimal:
        """
        Post-process the DMM value, if a special function was selected using :func:`set_function`. Returns the
        unmodified value if no special function was selected.

        Parameters
        ----------
        value: Decimal or float
            The value to post-process

        Returns
        -------
        Decimal
            the post-processed value. The value is unmodified if no special function was selected.
        """
        if self.__special_function is not None:
            try:
                return self.__convert_thermistor_to_temperature(value, self.__ntc_parameters)
            except ValueError:
                raise ValueError(f"Cannot convert resistance to temperature. Measurement was: {value}.") from None
        return value

    async def read(self, length: int | None = None) -> Decimal | bytes:
        """
        Read a single value from the device. If `length' is given, read `length` bytes, else read until a line break
        ``b"\\n"``.

        Parameters
        ----------
        length: int, optional
            The number of bytes to read. Omit to read a line.

        Returns
        -------
        Decimal or bytes
            Either a Decimal value or a number of bytes as defined by `length`.

        Raises
        ------
        OverflowError
            If the instrument input is overloaded, i.e. returns `+9.99999E+9`.
        """
        if length is None:
            result = (await self.__conn.read())[:-2]  # strip the EOT characters (\r\n)
        else:
            result = await self.__conn.read(length=length)

        match = numerical_test_pattern.match(result)
        if match is not None:
            if match[0] == b"+9.99999E+9":
                raise OverflowError("DMM input overloaded")
            return self.__post_process(Decimal(match[0].decode("ascii")))
        return result  # else return the bytes

    async def read_all(self, length: int | None = None) -> AsyncGenerator[Decimal | bytes, None]:
        """
        Read all values from the device. If `length' is given, read `length` bytes, else read until a line break
        ``b"\\n"``, then yield the result.

        Parameters
        ----------
        length: int, optional
            The number of bytes to read. Omit to read a line.

        Returns
        -------
        Iterator[Decimal or bytes]
            Either a Decimal value or a number of bytes as defined by `length`.

        Raises
        ------
        OverflowError
            If the instrument input is overloaded, i.e. returns `+9.99999E+9`.
        DeviceError
            If the device is not ready for read.
        asyncio.TimeoutError
            If the GPIB controller does not respond in time.
        """
        await self.set_srq_mask(SrqMask.DATA_READY)  # Enable a GPIB interrupt when the conversion is done
        while "loop not cancelled":
            try:
                status_byte = SerialPollFlags(await self.connection.wait((1 << 11) | (1 << 14)))
                if SerialPollFlags.SRQ_ON_DATA_READY in status_byte:
                    result = await self.read(length)
                    yield result
                else:
                    raise DeviceError(f"Device did not signal ready for read. Status was: {status_byte}")
            except asyncio.TimeoutError:
                raise asyncio.TimeoutError("The GPIB controller did not respond in time.") from None

    async def __query(self, command: bytes, length: int | None = None) -> bytes:
        await self.write(command)
        return await self.__conn.read(length=length)

    async def set_display(self, value: DisplayType, text: str = "") -> None:
        """
        Sets a custom display text or display measurands. See page 12 of the manual for details.

        Parameters
        ----------
        value: DisplayType
            The type of text to display on the front panel tft. If set to
            :attr:`DisplayType.NORMAL <hp3478a_async.enums.DisplayType.NORMAL>`, no text will be set.
        text: str
            The text to display if `value` is not set to
            :attr:`DisplayType.NORMAL <hp3478a_async.enums.DisplayType.NORMAL>`. There is no need to terminate the
            string with ``"\\r"`` or ``"\\n"``.
        """
        value = DisplayType(value)
        if value == DisplayType.NORMAL:
            # Do not allow text in normal display mode
            await self.write(f"D{value.value:d}".encode("ascii"))
        else:
            # The text must be terminated by a control character like \r or \n
            await self.write(f"D{value.value:d}{text.rstrip()}\n".encode("ascii"))

    async def set_trigger(self, value: TriggerType) -> None:
        """
        Set the DMM trigger. See page 53 of the manual for details.

        Parameters
        ----------
        value: TriggerType
            The trigger type used when taking measurements.
        """
        value = TriggerType(value)
        await self.write(f"T{value.value:d}".encode("ascii"))

    async def write(self, msg: bytes) -> None:
        """
        Write data or commands to the instrument. Do not terminate the command with a new line or carriage return
        (``b"\\r"`` or ``b"\\n"``). This bytestring will be written as is, be careful.

        Parameters
        ----------
        msg: bytes
            The string to be sent to the device.
        """
        await self.__conn.write(msg)

    async def set_srq_mask(self, value: SrqMask) -> None:
        """
        Set the service interrupt mask. This will determine, when the GPIB SRQ is triggered by the instrument. The
        :attr:`SrqMask.DATA_READY <hp3478a_async.flags.SrqMask.DATA_READY>` flag is useful, when reading with long
        conversion times. See :doc:`examples` for an example and page 46 of the manual for details.

        Parameters
        ----------
        value: SrqMask
            The service request register setting.
        """
        value = SrqMask(value)
        await self.write(f"M{value.value:02o}".encode("ascii"))

    async def get_front_rear_switch_position(self) -> FrontRearSwitchPosition:
        """
        Check whether the front or rear panel binding posts are active.

        Returns
        ----------
        FrontRearSwitchPosition
            The position of the front/rear switch
        """
        return FrontRearSwitchPosition(int(await self.__query(b"S")))

    async def device_clear(self) -> None:
        """
        Send the Selected Device Clear (SDC) event. This will trigger the self-test routine and  reset the device to
        its power on state.
        """
        await self.__conn.clear()

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
        Put the device in a certain measurement mode of either DVC, ACV, Ohms, 4-W Ohms, DCI, ACI or the extended ohms
        mode. See page 55 of the manual for details on the extended ohms mode.

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
        await self.write(f"F{value.value:d}".encode("ascii"))

    async def set_autozero(self, enable: bool) -> None:
        """
        Change the auto-zero mode of the DMM. If enabled, the DMM will auto-zero between readings.

        Parameters
        ----------
        enable: bool
            `True` to enable auto-zeroing.
        """
        enable = bool(enable)
        await self.write(f"Z{enable:d}".encode("ascii"))

    async def set_number_of_digits(self, value: int) -> None:
        """
        Set the number of digits returned by the DMM. This has an influence on the integration time.
        See page 15 of the manual for details.

        Parameters
        ----------
        value: {4, 5, 6}
            A value between 4 and 6.
        """
        value = int(value)
        assert 4 <= value <= 6
        await self.write(f"N{(value-1):d}".encode("ascii"))

    async def get_error_register(self) -> ErrorFlags:
        """
        Get the contents of the error register, which is the result of the power on self-test. See page 62 of the manual
        for details.

        Returns
        ----------
        ErrorFlags
            The error register
        """
        result = int(await self.__query(b"E"), base=8)  # Convert the octal result to int
        return ErrorFlags(result)

    async def set_range(self, value: Range) -> None:
        """
        Sets the measurement range. The range, that can be selected depend on the measurement mode.

        Parameters
        ----------
        value: Range
            The measurement range.
        """
        value = Range(value)
        await self.write(f"R{value.value}".encode("ascii"))

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
            FunctionType.DCV: -3,
            FunctionType.ACV: -2,
            FunctionType.OHM: 1,
            FunctionType.OHMF: 1,
            FunctionType.OHM_EXT: 1,
            FunctionType.DCI: -2,
            FunctionType.ACI: -2,
        }

        return Range(range_value + range_value_correction[function])

    async def get_cal_ram(self) -> bytes:
        """
        An undocumented function. Read the internal calibration memory from the NVRAM. It can be used to backup the
        calibration memory in case the internal battery fails. See :doc:`examples` for an example on how to read the
        memory and convert it to meaningful data.

        Returns
        ----------
        bytes
            The contents of the calibration ram.
        """
        result = bytearray()
        for addr in range(256):
            result.append(ord(await self.__query(command=bytes([ord("W"), addr]), length=1)))
        return bytes(result)

    async def set_cal_ram(self, data: bytes) -> None:
        """
        Write to the internal NVRAM. Warning: This can brick the device until a valid calibration
        configuration is written to the NVRAM. This function only works, if the front panel CAL switch is enabled.

        Parameters
        ----------
        data: bytes
            The data to be written to the calibration memory.
        """
        for addr, data_block in enumerate(data):
            await self.write(bytes([ord("X"), addr, data_block]))

    async def get_status(self) -> DmmStatus:
        """
        Read the binary status register of the device. See page 61 of the manual for details.

        Returns
        -------
        DmmStatus
            The current status of the DMM
        """
        # The "B" command is special. It does not contain a line terminator, the
        # device will output exactly 5 bytes and no more. So we need to read exactly
        # 5 bytes.
        result = await self.__query(command=b"B", length=5)
        function = FunctionType((result[0] >> 5) & 0b111)
        if self.__special_function is not None and function is FunctionType(
            ((self.__special_function.value - 8) % 2) + 3
        ):
            # If a special function is enabled in the driver, and the instrument is set to
            # the correct function, we will return the special function instead
            function = self.__special_function
        else:
            # If the correct function is not set on the device, we will disable the special function
            # in the driver
            self.__special_function = None
        return DmmStatus(
            function=function,
            range=self.__calculate_range(function, (result[0] >> 2) & 0b111),
            ndigits=6 - (result[0] & 0b11),
            status=StatusFlags(result[1]),
            srq_flags=SerialPollFlags(result[2]),
            error_flags=ErrorFlags(result[3]),
            dac_value=result[4],
        )

    async def serial_poll(self) -> SerialPollFlags:
        """
        Serial poll the device/GPIB controller. Use this in combination with the SRQ mask to determine, if the
        instrument triggered the SRQ and requests service.

        Returns
        -------
        SerialPollFlags
            The status register of the device
        """
        return SerialPollFlags(await self.__conn.serial_poll())
