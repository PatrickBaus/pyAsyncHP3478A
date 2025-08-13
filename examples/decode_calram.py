#!/usr/bin/env python3
# pylint: disable=duplicate-code
# ##### BEGIN GPL LICENSE BLOCK #####
#
# Copyright (C) 2021  Patrick Baus
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
"""This example shows how to decode calibration memory files of the HP 3478A"""
from hp3478a_async.hp_3478a_helper import decode_cal_data, encode_cal_data, format_cal_string


def main():
    """Decode the calibration memory file"""

    # Read the calibration memory file and strip the "\n" character at the end of each line.
    # Note: This will not work with Windows line endings ("\r\n")
    with open("calram_example.bin", encoding="utf-8") as filehandle:
        result = filehandle.read().replace("\n", "")

    is_cal_enabled, data = decode_cal_data(result)  # decode to CalramEntry
    print(f"File content:\n{result}")
    print("Was the calibration switch set to enabled when the file was created?", is_cal_enabled)
    print("Calram content:", "\n".join([str(entry) for entry in data]))
    print(f"Re-encoded calram:\n{format_cal_string(encode_cal_data(is_cal_enabled, data))}")


main()
