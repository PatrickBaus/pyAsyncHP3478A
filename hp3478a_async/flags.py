"""Flags are used for the status registers returned by the device."""
from __future__ import annotations

from enum import Flag


class SrqMask(Flag):
    """
    The service interrupt register flags. See page 47 of the manual for details.
    """

    NONE = 0b0
    DATA_READY = 1 << 0
    # Bit 1 is always 0
    SYNTAX_ERROR = 1 << 2
    HARDWARE_ERROR = 1 << 3
    FRONT_PANEL_SRQ = 1 << 4
    CALIBRATION_FAILURE = 1 << 5


class ErrorFlags(Flag):
    """
    The error register flags. See page 62 of the manual for details.
    """

    NONE = 0b0
    CAL_RAM_CHECKSUM = 1 << 0
    RAM_FAILURE = 1 << 1
    ROM_FAILURE = 1 << 2
    AD_SLOPE_CONVERGENCE = 1 << 3
    AD_SELFTEST_FAILURE = 1 << 4
    AD_LINK_FAILURE = 1 << 5


class StatusFlags(Flag):
    """
    The device status register flags. See page 61 of the manual for details.
    """

    NONE = 0b0
    INTERNAL_TRIGGER_ENABLED = 1 << 0
    AUTO_RANGE_ENABLED = 1 << 1
    AUTO_ZERO_ENABLED = 1 << 2
    LINE_FREQUENCY_50_HZ = 1 << 3
    FRONT_SWITCH_ENABLED = 1 << 4
    CAL_RAM_ENABLED = 1 << 5
    EXTERNAL_TRIGGER_ENABLED = 1 << 6
    # Bit 7 is always zero


class SerialPollFlags(Flag):
    """
    The serial poll flags as returned by SPOLL. See page 50 of the manual for details.
    """

    NONE = 0b0
    SRQ_ON_DATA_READY = 1 << 0
    # Bit 1 is always 0
    SRQ_ON_SYNTAX_ERROR = 1 << 2
    SRQ_ON_HARDWARE_ERROR = 1 << 3
    SRQ_ON_SRQ_BUTTON = 1 << 4
    SRQ_ON_CAL_FAILURE = 1 << 5
    SRQ_ON_HAS_SRQ = 1 << 6
    SRQ_ON_POWER_ON = 1 << 7
