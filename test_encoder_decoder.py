"""Unit test for the binary-coded decimal encoder/decoder used to encode/decode the calibration memory dumps."""
# ##### BEGIN GPL LICENSE BLOCK #####
#
# Copyright (C) 2020  Patrick Baus
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

import pytest

from hp3478a_async.hp_3478a_helper import _decode_gain_data, _encode_gain_data

encoder_data = [
    (1.055555, [0x5, 0x5, 0x5, 0x5, 0x5]),  # Maximum
    (0.955556, [0xC, 0xC, 0xC, 0xC, 0xC]),  # Minimum
    (1.000983, [0x0, 0x1, 0x0, 0xE, 0x3]),  # Taken from real HP3478A
    (1.000694, [0x0, 0x1, 0xD, 0xF, 0x4]),  # Taken from real HP3478A
    (1.000807, [0x0, 0x1, 0xE, 0x1, 0xD]),  # Taken from real HP3478A
    (1.000467, [0x0, 0x0, 0x5, 0xD, 0xD]),  # Taken from real HP3478A
    (1.000581, [0x0, 0x1, 0xC, 0xE, 0x1]),  # Taken from real HP3478A
    (1.001621, [0x0, 0x2, 0xC, 0x2, 0x1]),  # Taken from real HP3478A
    (1.004753, [0x0, 0x5, 0xD, 0x5, 0x3]),  # Taken from real HP3478A
    (1.005234, [0x0, 0x5, 0x2, 0x3, 0x4]),  # Taken from real HP3478A
    (1.004592, [0x0, 0x5, 0xC, 0xF, 0x2]),  # Taken from real HP3478A
    (1.004031, [0x0, 0x4, 0x0, 0x3, 0x1]),  # Taken from real HP3478A
    (1.004270, [0x0, 0x4, 0x3, 0xD, 0x0]),  # Taken from real HP3478A
    (1.004295, [0x0, 0x4, 0x3, 0xF, 0x5]),  # Taken from real HP3478A
    (1.013028, [0x1, 0x3, 0x0, 0x3, 0xE]),  # Taken from real HP3478A
    (1.012524, [0x1, 0x2, 0x5, 0x2, 0x4]),  # Taken from real HP3478A
    (1.000000, [0x0, 0x0, 0x0, 0x0, 0x0]),  # Taken from real HP3478A
    (1.016995, [0x2, 0xD, 0x0, 0xF, 0x5]),  # Taken from real HP3478A
    (1.000006, [0x0, 0x0, 0x0, 0x1, 0xC]),  # Synthetic, has multiple encodings
    (1.012906, [0x1, 0x3, 0xF, 0x1, 0xC]),  # Synthetic, has multiple encodings
    (1.046777, [0x5, 0xD, 0xE, 0xE, 0xD]),  # Synthetic
    (1.000770, [0x0, 0x1, 0xE, 0xD, 0x0]),  # Synthetic
    (1.046777, [0x5, 0xD, 0xE, 0xE, 0xD]),  # Synthetic
    (1.049000, [0x5, 0xF, 0x0, 0x0, 0x0]),  # Synthetic
    (0.988906, [0xF, 0xF, 0xF, 0x1, 0xC]),  # Synthetic
    (0.964445, [0xD, 0xB, 0xB, 0xB, 0xB]),  # Synthetic
    (0.975996, [0xE, 0xC, 0x0, 0x0, 0xC]),  # Synthetic
    (1.015996, [0x2, 0xC, 0x0, 0x0, 0xC]),  # Synthetic, has multiple encodings
]

decoder_data = encoder_data + [
    (1.000006, [0x0, 0x0, 0x0, 0x0, 0x6]),  # Synthetic, has multiple encodings
    (1.012906, [0x1, 0x3, 0xF, 0x0, 0x6]),  # Synthetic, has multiple encodings
    (1.015996, [0x1, 0x6, 0x0, 0xF, 0x6]),  # Synthetic, has multiple encodings
]


@pytest.mark.parametrize("decoded_gain_data, encoded_gain_data", encoder_data)
def test_gain_encoder(decoded_gain_data, encoded_gain_data):
    """Test the gain encoder again known good data."""
    assert _encode_gain_data(decoded_gain_data) == encoded_gain_data


@pytest.mark.parametrize(
    "decoded_gain_data",
    [
        1.077777,
        1.055556,
    ],
)
def test_gain_encoder_too_high(decoded_gain_data):
    """Test the gain encoder against known bad data, causing an overflow."""
    with pytest.raises(OverflowError):
        _encode_gain_data(decoded_gain_data)


@pytest.mark.parametrize(
    "decoded_gain_data",
    [
        0.955555,
        0.944445,  # = 1 - (1.055555-1)
        0.911112,
    ],
)
def test_gain_encoder_too_low(decoded_gain_data):
    """Test the gain encoder against known bad data, causing an overflow."""
    with pytest.raises(OverflowError):
        _encode_gain_data(decoded_gain_data)


@pytest.mark.parametrize("decoded_gain_data, encoded_gain_data", decoder_data)
def test_gain_decoder(decoded_gain_data, encoded_gain_data):
    """Test the gain decoder against known good data"""
    assert _decode_gain_data(encoded_gain_data) == decoded_gain_data
