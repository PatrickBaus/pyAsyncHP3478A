"""Unit tests for the commands of the HP 3478A driver using a fake GPIB connection (no hardware required)."""

from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest

from hp3478a_async import HP_3478A, FunctionType, Range
from hp3478a_async.enums import DisplayType, FrontRearSwitchPosition, TriggerType
from hp3478a_async.flags import ErrorFlags, SerialPollFlags, SrqMask
from tests.test_hp3478a import FakeConnection


class FakePrologixConnection(FakeConnection):
    """A fake connection, that has the set_eot() method of the Prologix adapters."""

    def __init__(self) -> None:
        super().__init__()
        self.eot: bool | None = None

    async def set_eot(self, value: bool) -> None:
        """Record the EOT setting."""
        self.eot = value


@pytest.fixture(name="no_sleep")
def fixture_no_sleep(monkeypatch):
    """disconnect() waits 0.5 s for the device. Skip the wait to keep the tests fast."""
    original_sleep = asyncio.sleep

    async def sleep(_delay, *args, **kwargs):
        return await original_sleep(0, *args, **kwargs)

    monkeypatch.setattr(asyncio, "sleep", sleep)


def run(coroutine):
    """Run a coroutine in a new event loop."""
    return asyncio.run(coroutine)


def test_str():
    """The string representation contains the connection."""
    assert str(HP_3478A(FakeConnection())) == "HEWLETT-PACKARD 3478A at FakeConnection"


def test_connection_property():
    """The connection passed to the constructor is available as a property."""
    conn = FakeConnection()
    assert HP_3478A(conn).connection is conn


def test_get_id():
    """The device has no ID command, so the ID is a constant."""
    assert run(HP_3478A.get_id()) == ("HEWLETT-PACKARD", "3478A", "0", "0")


def test_connect_disables_eot_on_prologix():
    """The Prologix adapters must not append an EOT character."""
    conn = FakePrologixConnection()
    run(HP_3478A(conn).connect())
    assert conn.eot is False


@pytest.mark.usefixtures("no_sleep")
def test_context_manager():
    """The context manager connects, returns the device to local mode and disconnects."""
    conn = FakeConnection()

    async def use_context_manager():
        async with HP_3478A(conn) as dmm:
            assert isinstance(dmm, HP_3478A)
            assert conn.calls == ["connect"]

    run(use_context_manager())
    assert conn.calls == ["connect", "ibloc", "disconnect"]


@pytest.mark.usefixtures("no_sleep")
def test_disconnect_ignores_connection_error():
    """If the device cannot be returned to local mode, the connection must still be closed."""
    conn = FakeConnection()
    conn.fail_local = True
    run(HP_3478A(conn).disconnect())
    assert conn.calls == ["disconnect"]


@pytest.mark.parametrize(
    "display, text, expected",
    [
        (DisplayType.NORMAL, "ignored", b"D1"),
        (DisplayType.SHOW_TEXT, "HELLO  ", b"D2HELLO\n"),
        (DisplayType.SHOW_TEXT_AND_FREEZE, "FROZEN", b"D3FROZEN\n"),
    ],
)
def test_set_display(display, text, expected):
    """The text is only sent, if the display does not show the measurements."""
    conn = FakeConnection()
    run(HP_3478A(conn).set_display(display, text))
    assert conn.written == [expected]


@pytest.mark.parametrize(
    "coroutine_function, argument, expected",
    [
        (HP_3478A.set_trigger, TriggerType.SINGLE, b"T3"),
        (HP_3478A.set_srq_mask, SrqMask.DATA_READY | SrqMask.SYNTAX_ERROR, b"M05"),
        (HP_3478A.set_srq_mask, SrqMask.CALIBRATION_FAILURE | SrqMask.FRONT_PANEL_SRQ, b"M60"),
        (HP_3478A.set_function, FunctionType.ACI, b"F6"),
        (HP_3478A.set_autozero, True, b"Z1"),
        (HP_3478A.set_autozero, 0, b"Z0"),
        (HP_3478A.set_number_of_digits, 4, b"N3"),
        (HP_3478A.set_range, Range.RANGE_30k, b"R4"),
        (HP_3478A.set_range, Range.RANGE_30M, b"R-2"),
        (HP_3478A.set_range, Range.RANGE_AUTO, b"RA"),
        (HP_3478A.write, b"F1R0", b"F1R0"),
    ],
)
def test_commands_with_argument(coroutine_function, argument, expected):
    """The settings are sent as the commands described in the manual."""
    conn = FakeConnection()
    run(coroutine_function(HP_3478A(conn), argument))
    assert conn.written == [expected]


@pytest.mark.parametrize(
    "coroutine_function, expected", [(HP_3478A.clear, b"K"), (HP_3478A.reset, b"H0")], ids=["clear", "reset"]
)
def test_commands_without_argument(coroutine_function, expected):
    """Commands without parameters."""
    conn = FakeConnection()
    run(coroutine_function(HP_3478A(conn)))
    assert conn.written == [expected]


@pytest.mark.parametrize("value", [3, 7])
def test_set_number_of_digits_out_of_range(value):
    """Only 4, 5 or 6 digits are supported."""
    conn = FakeConnection()
    with pytest.raises(AssertionError):
        run(HP_3478A(conn).set_number_of_digits(value))
    assert not conn.written


@pytest.mark.parametrize("invalid_value", [0, "foo"])
def test_invalid_enum_values_are_rejected(invalid_value):
    """Values, that are not part of the enum, are rejected before anything is sent."""
    conn = FakeConnection()
    dmm = HP_3478A(conn)
    for coroutine_function in (dmm.set_display, dmm.set_trigger, dmm.set_function):
        with pytest.raises(ValueError):
            run(coroutine_function(invalid_value))
    assert not conn.written


def test_device_clear():
    """The Selected Device Clear is a GPIB command, not a device message."""
    conn = FakeConnection()
    run(HP_3478A(conn).device_clear())
    assert conn.calls == ["clear"]
    assert not conn.written


def test_local():
    """local() returns the device to local mode using the GPIB connection."""
    conn = FakeConnection()
    run(HP_3478A(conn).local())
    assert conn.calls == ["ibloc"]


@pytest.mark.parametrize(
    "response, expected", [(b"0\r\n", FrontRearSwitchPosition.REAR), (b"1\r\n", FrontRearSwitchPosition.FRONT)]
)
def test_get_front_rear_switch_position(response, expected):
    """The switch position is queried with the "S" command."""
    conn = FakeConnection()
    conn.read_response = response
    assert run(HP_3478A(conn).get_front_rear_switch_position()) is expected
    assert conn.written == [b"S"]


@pytest.mark.parametrize(
    "response, expected",
    [
        (b"00\r\n", ErrorFlags.NONE),
        (b"01\r\n", ErrorFlags.CAL_RAM_CHECKSUM),
        (b"77\r\n", ~ErrorFlags.NONE),  # The register is returned as an octal number
        (b"40\r\n", ErrorFlags.AD_LINK_FAILURE),
    ],
)
def test_get_error_register(response, expected):
    """The error register is queried with the "E" command and returned as an octal number."""
    conn = FakeConnection()
    conn.read_response = response
    assert run(HP_3478A(conn).get_error_register()) == expected
    assert conn.written == [b"E"]


def test_serial_poll():
    """The serial poll is forwarded to the connection."""
    conn = FakeConnection()
    conn.status_byte = (SerialPollFlags.SRQ_ON_POWER_ON | SerialPollFlags.SRQ_ON_HAS_SRQ).value
    assert run(HP_3478A(conn).serial_poll()) == SerialPollFlags.SRQ_ON_POWER_ON | SerialPollFlags.SRQ_ON_HAS_SRQ


def test_get_status_flags():
    """The status, SRQ and error registers and the DAC value are decoded from the "B" response."""
    conn = FakeConnection()
    conn.read_response = bytes([(FunctionType.ACI.value << 5) | (3 << 2) | 2, 0b10, 0b1000001, 0b100, 0xAB])
    status = run(HP_3478A(conn).get_status())
    assert conn.written == [b"B"]
    assert status.function is FunctionType.ACI
    assert status.range is Range.RANGE_30
    assert status.ndigits == 5
    assert status.status.value == 0b10
    assert status.srq_flags == SerialPollFlags.SRQ_ON_DATA_READY | SerialPollFlags.SRQ_ON_HAS_SRQ
    assert status.error_flags is ErrorFlags.ROM_FAILURE
    assert status.dac_value == 0xAB


def test_get_cal_ram():
    """The calibration memory is read one byte at a time using the "W" command."""
    conn = FakeConnection()
    conn.read_response = b"@"
    assert run(HP_3478A(conn).get_cal_ram()) == b"@" * 256
    assert conn.written == [bytes([ord("W"), addr]) for addr in range(256)]


def test_set_cal_ram():
    """The calibration memory is written one byte at a time using the "X" command."""
    conn = FakeConnection()
    data = bytes([0x40, 0x4F, 0x41])
    run(HP_3478A(conn).set_cal_ram(data))
    assert conn.written == [b"X\x00\x40", b"X\x01\x4f", b"X\x02\x41"]


@pytest.mark.parametrize(
    "length, response, expected",
    [
        (None, b"+1.23456E-3\r\n", Decimal("1.23456E-3")),
        (None, b"-1.23456E+0\r\n", Decimal("-1.23456")),
        (None, b"not a number\r\n", b"not a number"),  # Non-numerical responses are returned as bytes
        (5, b"\x01\x02\x03\x04\x05", b"\x01\x02\x03\x04\x05"),  # The length is read as is, without stripping
        (11, b"+1.00000E+1", Decimal("10")),
    ],
)
def test_read(length, response, expected):
    """read() returns numerical values as Decimal and everything else as bytes."""
    conn = FakeConnection()
    conn.read_response = response
    assert run(HP_3478A(conn).read(length)) == expected


@pytest.mark.parametrize("function", [FunctionType.NTC, FunctionType.NTCF])
def test_read_thermistor(function):
    """In thermistor mode, the resistance is converted to a temperature in K."""
    conn = FakeConnection()
    dmm = HP_3478A(conn)
    run(dmm.set_function(function))
    conn.read_response = b"+1.00000E+4\r\n"  # R25 of the default thermistor
    assert run(dmm.read()) == pytest.approx(Decimal("298.15"), abs=Decimal("0.01"))


def test_read_thermistor_custom_parameters():
    """The NTC parameters can be changed."""
    conn = FakeConnection()
    dmm = HP_3478A(conn)
    dmm.set_ntc_parameters(a=1 / 300, b=1e-4, c=0, d=0, rt25=5e3)
    run(dmm.set_function(FunctionType.NTC))
    conn.read_response = b"+5.00000E+3\r\n"
    assert float(run(dmm.read())) == pytest.approx(300)


def test_read_thermistor_invalid_resistance():
    """A resistance, that cannot be converted to a temperature, must raise a ValueError with the measurement."""
    conn = FakeConnection()
    dmm = HP_3478A(conn)
    run(dmm.set_function(FunctionType.NTC))
    conn.read_response = b"-1.00000E+4\r\n"
    with pytest.raises(ValueError, match="Measurement was: -10000"):
        run(dmm.read())


def test_set_function_clears_special_function():
    """Selecting a normal function after a thermistor function disables the conversion."""
    conn = FakeConnection()
    dmm = HP_3478A(conn)
    run(dmm.set_function(FunctionType.NTC))
    run(dmm.set_function(FunctionType.OHM))
    conn.read_response = b"+1.00000E+4\r\n"
    assert run(dmm.read()) == Decimal("1.00000E+4")


def test_read_all_yields_multiple_values():
    """read_all() keeps reading, until the generator is closed."""
    conn = FakeConnection()
    conn.status_byte = (SerialPollFlags.SRQ_ON_DATA_READY | SerialPollFlags.SRQ_ON_HAS_SRQ).value
    conn.read_response = b"+1.23456E+0\r\n"

    async def read_three():
        generator = HP_3478A(conn).read_all()
        try:
            return [await anext(generator) for _ in range(3)]
        finally:
            await generator.aclose()

    assert run(read_three()) == [Decimal("1.23456")] * 3
    assert conn.written == [b"M01"]  # The SRQ on data ready is enabled once
