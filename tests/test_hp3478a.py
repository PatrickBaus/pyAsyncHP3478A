"""Unit tests for the HP 3478A driver using a fake GPIB connection (no hardware required)."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import override

import pytest

from hp3478a_async import HP_3478A, DmmStatus, FunctionType, NtcParameters, Range
from hp3478a_async.errors import DeviceError
from hp3478a_async.flags import SerialPollFlags
from hp3478a_async.hp_3478a_helper import decode_cal_data, encode_cal_data, format_cal_string


class FakeConnection:  # pylint: disable=missing-function-docstring,too-many-instance-attributes
    """Minimal stand-in for AsyncGpib / AsyncPrologixGpibController."""

    def __init__(self, *, wait_returns_status: bool = True) -> None:
        self.written: list[bytes] = []
        self.read_response: bytes = b""
        self.status_byte: int = 0
        self.wait_returns_status = wait_returns_status
        self.wait_timeout = False
        self.fail_writes = False
        self.serial_polls = 0
        self.fail_local = False
        self.calls: list[str] = []

    @override
    def __str__(self) -> str:
        return "FakeConnection"

    async def connect(self) -> None:
        self.calls.append("connect")

    async def disconnect(self) -> None:
        self.calls.append("disconnect")

    async def clear(self) -> None:
        self.calls.append("clear")

    async def ibloc(self) -> None:
        if self.fail_local:
            raise ConnectionError("Connection lost")
        self.calls.append("ibloc")

    async def write(self, msg: bytes) -> None:
        await asyncio.sleep(0)  # Let other tasks run, like a real connection would
        if self.fail_writes:
            raise ConnectionError("Connection lost")
        self.written.append(msg)

    async def read(self, length: int | None = None) -> bytes:  # pylint: disable=unused-argument
        return self.read_response

    async def wait(self, mask: int) -> int | None:  # pylint: disable=unused-argument
        if self.wait_timeout:
            raise TimeoutError("Timeout waiting for event.")
        # prologix-gpib-async returns the status byte, async-gpib (linux-gpib) returns None
        return self.status_byte if self.wait_returns_status else None

    async def serial_poll(self) -> int:
        self.serial_polls += 1
        return self.status_byte


def make_dmm(conn: FakeConnection) -> HP_3478A:
    """Create a DMM, that uses the fake connection."""
    # FakeConnection is not a GpibConnection. The ignore is unused if the adapter libraries are not installed.
    return HP_3478A(conn)  # type: ignore[arg-type,unused-ignore]


def status_bytes(function: int, range_code: int, digits_code: int) -> bytes:
    """Build the 5 byte response to the "B" command."""
    return bytes([(function << 5) | (range_code << 2) | digits_code, 0, 0, 0, 0])


def get_status(conn: FakeConnection, dmm: HP_3478A | None = None) -> DmmStatus:
    """Run get_status() on a new or the given DMM."""
    dmm = dmm or make_dmm(conn)
    return asyncio.run(dmm.get_status())


@pytest.mark.parametrize(
    "function, range_code, expected",
    [
        (FunctionType.DCV, 1, Range.RANGE_30M),
        (FunctionType.DCV, 5, Range.RANGE_300),
        (FunctionType.ACV, 1, Range.RANGE_300M),
        (FunctionType.DCI, 2, Range.RANGE_3),
        (FunctionType.OHM, 1, Range.RANGE_30),  # most sensitive ohms range is 30 Ω
        (FunctionType.OHM, 4, Range.RANGE_30k),
        (FunctionType.OHM, 7, Range.RANGE_30MEG),  # used to raise ValueError
        (FunctionType.OHMF, 7, Range.RANGE_30MEG),
        (FunctionType.OHM_EXT, 7, Range.RANGE_30MEG),
    ],
)
def test_status_range(function: FunctionType, range_code: int, expected: Range) -> None:
    """The range bits of the status byte must map to the correct Range for each function."""
    conn = FakeConnection()
    conn.read_response = status_bytes(function.value, range_code, 1)
    assert get_status(conn).range is expected


@pytest.mark.parametrize("ndigits", [4, 5, 6])
def test_number_of_digits_round_trip(ndigits: int) -> None:
    """The value passed to set_number_of_digits() must be reported back by get_status()."""
    conn = FakeConnection()
    dmm = make_dmm(conn)
    asyncio.run(dmm.set_number_of_digits(ndigits))
    n_command = int(conn.written[-1][1:])  # N3, N4 or N5
    digits_code = 6 - n_command  # N5 = 5½ -> 1, N4 = 4½ -> 2, N3 = 3½ -> 3
    conn.read_response = status_bytes(FunctionType.DCV.value, 3, digits_code)
    assert get_status(conn, dmm).ndigits == ndigits


@pytest.mark.parametrize("special, device_function", [(FunctionType.NTC, 3), (FunctionType.NTCF, 4)])
def test_status_in_thermistor_mode(special: FunctionType, device_function: int) -> None:
    """get_status() must not fail and must report the special function in thermistor mode."""
    conn = FakeConnection()
    dmm = make_dmm(conn)
    asyncio.run(dmm.set_function(special))
    assert conn.written[-1] == f"F{device_function}".encode()
    conn.read_response = status_bytes(device_function, 4, 1)
    status = get_status(conn, dmm)  # used to raise KeyError
    assert status.function is special
    assert status.range is Range.RANGE_30k


def test_status_clears_special_function_on_mode_change() -> None:
    """Switching the device to another function must disable the thermistor conversion."""
    conn = FakeConnection()
    dmm = make_dmm(conn)
    asyncio.run(dmm.set_function(FunctionType.NTC))
    conn.read_response = status_bytes(FunctionType.DCV.value, 3, 1)
    assert get_status(conn, dmm).function is FunctionType.DCV
    conn.read_response = b"+1.00000E+3\r\n"
    assert asyncio.run(dmm.read()) == Decimal("1.00000E+3")  # no thermistor conversion anymore


async def _first_reading(dmm: HP_3478A) -> Decimal | bytes:
    generator = dmm.read_all()
    try:
        return await anext(generator)
    finally:
        await generator.aclose()


@pytest.mark.parametrize("wait_returns_status", [True, False], ids=["prologix", "linux-gpib"])
def test_read_all(wait_returns_status: bool) -> None:
    """read_all() must work with both GPIB backends."""
    conn = FakeConnection(wait_returns_status=wait_returns_status)
    conn.status_byte = (SerialPollFlags.SRQ_ON_DATA_READY | SerialPollFlags.SRQ_ON_HAS_SRQ).value
    conn.read_response = b"+1.23456E+0\r\n"
    assert asyncio.run(_first_reading(make_dmm(conn))) == Decimal("1.23456")
    # linux-gpib does not return the status byte from wait(), so it must be serial polled
    assert conn.serial_polls == (0 if wait_returns_status else 1)


def test_read_overload() -> None:
    """An overloaded input must raise an OverflowError."""
    conn = FakeConnection()
    conn.read_response = b"+9.99999E+9\r\n"
    with pytest.raises(OverflowError):
        asyncio.run(make_dmm(conn).read())


def test_ntc_parameters_allow_zero_and_negative_higher_order_terms() -> None:
    """Only R25 is validated, the higher order coefficients may be zero or negative."""
    dmm = make_dmm(FakeConnection())
    dmm.set_ntc_parameters(a=1.129e-3, b=2.341e-4, c=0, d=-1e-8, rt25=10e3)  # used to fail the assert
    with pytest.raises(ValueError):
        dmm.set_ntc_parameters(a=1e-3, b=2e-4, c=0, d=0, rt25=0)


def _calram() -> bytes:
    # 1 cal enable nibble + 19 blocks of zero offset, unity gain + 8 padding nibbles
    block = [0] * 11
    checksum = 0xFF - sum(block)
    block += [checksum >> 4, checksum & 0xF]
    return bytes(value + 0x40 for value in [0] + block * 19 + [0] * 8)


def test_encode_cal_data_accepts_iterators() -> None:
    """encode_cal_data() must accept iterators and still check the number of entries."""
    is_cal_enabled, entries = decode_cal_data(_calram())
    assert encode_cal_data(is_cal_enabled, iter(entries)) == _calram()
    with pytest.raises(TypeError):
        encode_cal_data(is_cal_enabled, iter(entries[:-1]))


def _data_ready_connection() -> FakeConnection:
    conn = FakeConnection()
    conn.status_byte = (SerialPollFlags.SRQ_ON_DATA_READY | SerialPollFlags.SRQ_ON_HAS_SRQ).value
    conn.read_response = b"+1.23456E+0\r\n"
    return conn


def test_read_all_timeout() -> None:
    """A GPIB timeout must be raised as a TimeoutError with a clear message."""
    conn = _data_ready_connection()
    conn.wait_timeout = True
    with pytest.raises(TimeoutError, match="did not respond in time"):
        asyncio.run(_first_reading(make_dmm(conn)))
    # asyncio.TimeoutError is the same class since Python 3.11, so existing handlers keep working
    assert asyncio.TimeoutError is TimeoutError


def test_read_all_device_not_ready() -> None:
    """read_all() must raise a DeviceError, if the device requested service for a reason other than data ready."""
    conn = _data_ready_connection()
    conn.status_byte = (SerialPollFlags.SRQ_ON_SYNTAX_ERROR | SerialPollFlags.SRQ_ON_HAS_SRQ).value
    with pytest.raises(DeviceError):
        asyncio.run(_first_reading(make_dmm(conn)))


def test_read_all_does_not_reword_exceptions_thrown_in() -> None:
    """A TimeoutError thrown into the generator by the caller is not a GPIB timeout and must not be reworded."""

    async def throw_into_generator() -> None:
        generator = make_dmm(_data_ready_connection()).read_all()
        await anext(generator)
        try:
            await generator.athrow(TimeoutError("caller timeout"))
        finally:
            await generator.aclose()

    with pytest.raises(TimeoutError, match="caller timeout"):
        asyncio.run(throw_into_generator())


def test_dataclasses_are_slotted() -> None:
    """The status and NTC parameter dataclasses use __slots__."""
    conn = FakeConnection()
    conn.read_response = status_bytes(FunctionType.DCV.value, 3, 1)
    status = get_status(conn)
    with pytest.raises(AttributeError):
        status.unknown_attribute = 1  # type: ignore[attr-defined]  # pylint: disable=assigning-non-slot


def test_connect_sends_default_settings() -> None:
    """connect() must send the default display mode and SRQ mask, in that order."""
    conn = FakeConnection()
    asyncio.run(make_dmm(conn).connect())
    assert conn.written == [b"D1", b"M00"]


def test_connect_raises_plain_connection_error() -> None:
    """The settings are sent in a TaskGroup, but errors must not be wrapped in an ExceptionGroup."""
    conn = FakeConnection()
    conn.fail_writes = True
    with pytest.raises(ConnectionError):
        asyncio.run(make_dmm(conn).connect())


def test_dataclasses_are_keyword_only() -> None:
    """The fields of NtcParameters (and DmmStatus) can only be passed by keyword."""
    with pytest.raises(TypeError):
        # This call is meant to fail
        NtcParameters(3.354e-3, 2.787e-4, 4.0e-6, 1.6e-7, 10e3)  # type: ignore[call-arg]  # pylint: disable=E1121,E1125
    parameters = NtcParameters(a=3.354e-3, b=2.787e-4, c=4.0e-6, d=1.6e-7, rt25=10e3)
    assert parameters.rt25 == 10e3


def test_format_cal_string() -> None:
    """The calibration memory is formatted as 16 lines of 16 characters each."""
    data = _calram()
    lines = format_cal_string(data).split("\n")
    assert len(lines) == 16
    assert all(len(line) == 16 for line in lines)
    assert "".join(lines).encode() == data
    assert decode_cal_data("".join(lines)) == decode_cal_data(data)
