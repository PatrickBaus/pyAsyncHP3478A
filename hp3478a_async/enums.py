"""Enums are used to represent the device functions and settings."""
from __future__ import annotations

from enum import Enum


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
    RANGE_3k = 3  # small k due to SI pylint: disable=invalid-name
    RANGE_30k = 4  # small k due to SI pylint: disable=invalid-name
    RANGE_300k = 5  # small k due to SI pylint: disable=invalid-name
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
