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
Helper functions to encode and decode data formats used by the HP 3478A.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CalramEntry:
    """One out of 19 calibration memory entries, that contain the gain, offset and checksum."""

    offset: int
    gain: float
    checksum: int
    is_valid: bool

    def __init__(self, data_block: list[int] | tuple[int, ...]) -> None:
        calculated_checksum = _calculate_cal_checksum(data_block)
        offset_block, gain_block, checksum_block = data_block[:6], data_block[6:11], data_block[11:]
        self.checksum = (checksum_block[0] << 4) + checksum_block[1]
        self.offset = _decode_offset_data(offset_block)
        self.gain = _decode_gain_data(gain_block)
        self.is_valid = calculated_checksum == self.checksum

    def to_bytes(self) -> bytes:
        """
        Return the offset and gain as a bytestring. The checksum will be recalculated.

        Returns
        -------
        bytes
            The bytestring which can be written to the HP 3478A.
        """
        result = _encode_offset_data(self.offset) + _encode_gain_data(self.gain)
        checksum = _calculate_cal_checksum(result)
        result += [(checksum >> 4) & 0xF, (checksum >> 0) & 0xF]

        return bytes([value + 0x40 for value in result])


def format_cal_string(data: bytes) -> str:
    """
    Convert the calibration memory to a unicode string with only ASCII characters.

    Parameters
    ----------
    data: bytes
        The calram contents

    Returns
    -------
    str
        A human readable string with ASCII characters.
    """
    return "\n".join([(data[i : i + 16]).decode() for i in range(0, len(data), 16)])


def _decode_bcd_8421(data: list[int] | tuple[int, ...]) -> int:
    result = 0
    for i, value in enumerate(reversed(data)):
        result += 10**i * value

    return result


def _encode_bcd_8421(value: int) -> list[int]:
    return [int(i) for i in str(value)]


def _decode_offset_data(data: list[int] | tuple[int, ...]) -> int:
    # The offset is BCD 8421 encoded, so only 4 bits are required per number
    # not a full byte
    result = _decode_bcd_8421(data)

    # If the raw value is >= 900000, it is negative.
    # This means 900000 => -100000, 999999 => -1
    result = result if result < 900000 else result - 1000000
    return result


def _encode_offset_data(value: int) -> list[int]:
    assert -100000 <= value <= 899999

    value = value if value >= 0 else value + 1000000
    # The offset is BCD 8421 encoded, so only 4 bits are required per number
    # not a full byte
    result = _encode_bcd_8421(value)
    # Pad with null bytes to return a bytestring of length 6
    return [0] * (6 - len(result)) + result


def _decode_gain_data(data: list[int] | tuple[int, ...]) -> float:
    # The gain is BCD 8421 encoded. Additionally, each byte is a
    # 4-bit two's complement signed number, hence if the 4th bit is set,
    # the number is negative. Finally, the gain is given in ppm offset from 1.
    # Start by decoding the two's complement
    result_raw = [value - 0x10 if value & 0x08 else value for value in data]
    # Then decode the BCD 8421
    result = _decode_bcd_8421(result_raw)
    # finally convert it to the gain
    return 1.0 + (result / 10**6)


def _encode_digit(number: int):
    result = [int(x) for x in str(number)]
    result = [0] * (2 - len(result)) + result
    if result[1] > 5:
        result[0] += 1
        result[1] -= 10
    return result


def _encode_gain_data(value: float) -> list[int]:
    # Encoding the gain is a little more tricky than decoding. The data that needs to be encoded is
    # the deviation in ppm from a gain of 1.
    # Coming from the binary format, we can see that we have 5 bytes, each consisting of only 4 bits of
    # data due to the BCD 8421 encoding chosen.
    # The designers also needed negative numbers, but this is a problem, because the set of numbers is
    # {-9,...,9}, which is 19 numbers and 4 bits are only 15 numbers. The designers chose 4-bit
    # two's complement for their signed numbers. So the set of available numbers is {-8,...,7}.
    # Here are a few examples how numbers can be represented in this system:
    # 9 = 10 + (-1) => [1, -1]
    # 8 = 10 + (-2) => [1, -2]
    # 7 => [0, 7]
    # -8 => [0, -8]
    # -9 => -10 + 1 => [-1, 1]
    # The original 8048 CPU has a half-carry flag to make this easier.
    # To make matters worse, there are several ways to encode a number this way. The
    # HP3478A seems not to use numbers greater than 5 (although 6,7 would be encodable) or numbers
    # less than -5. (In byte notation: 0x6, 0x7, 0x8 (-8), 0x9 (-7), 0xA (-6), 0xB (-5))
    # This reduces the set of available numbers to to {-4,...,5}.

    if not 0.955556 <= value <= 1.055555:
        raise OverflowError()

    value = int(round((value - 1.0) * 10**6))

    digits = _encode_bcd_8421(abs(value))
    # Pad with null bytes to return a bytestring of length 5
    digits = [0] * (5 - len(digits)) + digits
    result = [0] * 5

    for idx in reversed(range(len(digits))):
        carry, digit = _encode_digit(result[idx] + digits[idx])
        result[idx] = digit
        if idx == 0 and carry != 0:
            raise OverflowError()
        result[idx - 1] += carry

    result = [num if num >= 0 else num + 16 for num in result]

    if value < 0:
        result = [(~item + 1) & 0xF for item in result]
    return result


def _calculate_cal_checksum(data: list[int] | tuple[int, ...]) -> int:
    # The checksum is 0xFF minus the sum over the 11 data bytes
    calculated_checksum = 0xFF - (sum(data[:11]) & 0xFF)  # We need to truncate to uin8_t

    return calculated_checksum


def decode_cal_data(encoded_data: str | bytes) -> tuple[bool, tuple[CalramEntry, ...]]:
    """
    The calibration data is stored as nibbles (4 bit, half-bytes). This function decodes the contents
    of the calibration ram and returns the status of the calibration switch.

    Returns
    ----------
    tuple[bool, dict]
        `True` if the calibration switch is enabled and the calibration constants as a dict
    """
    if isinstance(encoded_data, str):
        # If we receive a unicode string, we will try to encode it to bytes
        encoded_data = encoded_data.encode("ascii")
    # The first nibble (4 bit, half-byte) contains the position of the front panel "CAL ENABLE" switch
    # data[0] = 0x0 if(CAL ENABLE) else 0xF
    # This byte does not contribute to the checksum and needs to be removed
    # The last 8 bytes are unused as well
    # The actual data is 19 blocks (one for calibration entry) of 11 bytes data + 2 bytes checksum = 247 bytes
    # Three blocks are not used for data, so their checksums do not matter: Blocks 6, 17 and 19
    block_size = 13
    # All data but the checksum is BCD 8421 (https://en.wikipedia.org/wiki/Binary-coded_decimal) encoded. This requires
    # 4 bits per decimal digit. After BCD encoding all bytes are encoded to printable characters adding 0x40.
    # So we need to subtract 0x40 first, before decoding the characters.
    data = [value - 0x40 for value in encoded_data]

    is_cal_enabled = data[0] == 0x0

    # Strip off non-data bytes
    data = data[1:248]
    # Split the string into substrings of length block_size
    data_blocks = [(data[i : i + block_size]) for i in range(0, len(data), block_size)]

    # Now decode the data block
    # 1. calculate and test the checksum of the data block
    # 2. decode the block and split it into its 3 components
    return is_cal_enabled, tuple(CalramEntry(data_block) for data_block in data_blocks)


def encode_cal_data(cal_enable: bool, data_blocks: tuple[CalramEntry, ...] | list[CalramEntry]) -> bytes:
    """
    The calibration data is stored as nibbles (4 bit, half-bytes). This function encodes a
    dictionary with the calibration constants to bytes.

    Parameters
    ----------
    data_blocks: list[dict[str, bool or int or float]]
        The calibration data
    cal_enable:
        Set to `True`, to write the calibration data to the NVRAM.
    """
    encoded_data_blocks = b"".join([entry.to_bytes() for entry in data_blocks])

    # Put the range check here, because this enables the use of iterators as input
    if len(data_blocks) != 19:
        raise TypeError("Invalid number of calibration constants")

    # Finally, pad with the cal_enable byte at the beginning and 8 0 bytes at the end
    result = bytes([0xF * bool(not cal_enable) + 0x40]) + encoded_data_blocks + bytes([0 + 0x40] * 8)
    return result
