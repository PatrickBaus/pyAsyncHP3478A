Calibration Memory
==================
The HP 3478A has a battery backed calibration memory. It is recommended to create a backup of that memory in case the
battery fails. This library supports backing up the calibration memory and also modifying it. This allows the user to
change the calibration constants while the library does all the checksum calculations in the background.

Backing up the calibration memory
---------------------------------

To back up the calibration memory use the following python scrip also found in the
`examples folder <https://github.com/PatrickBaus/pyAsyncHP3478A/tree/master/examples/>`_. This script will copy the
calibration memory to a file called `calram.bin`. Note: It will not overwrite the file and error out if it already
exists.

.. literalinclude:: ../../examples/read_calram.py
    :language: python

Writing the backup back to the DMM
----------------------------------
The backup can be written back to the dmm using another script. To do so, the ``CAL`` switch on the front panel must be
set to `enable`. Otherwise the memory cannot be written to.

.. literalinclude:: ../../examples/write_calram.py
    :language: python

Technical details
-----------------
The calibration memory dump is a human-readable ASCII string, that contain only printable characters. This was done by
adding ``0x40`` to each byte. After subtracting ``0x40``, the result is  a mix of bytes and
`nibbles <https://en.wikipedia.org/wiki/Nibble>`_ (4 bit, half-bytes). The calibration data is stored as nibbles, while
the checksum and the status of the ``CAL`` switch have 8 bit boundaries. The first byte of the memory dump contain said
``CAL`` switch position and
is not part of the checksum-protected calibration data. The calibration memory is stored as
nibbles which contain
`Binary-coded decimal (BCD) <https://en.wikipedia.org/wiki/Binary-coded_decimal>`_
encoded digits. The encoding is similar to BCD 8421. At the end there are two bytes for the checksum. The memory layout
is:

+-------------------------------------+
|            Memory Layout            |
+----------------+--------------------+
|       0        |        1:247       |
+================+====================+
| ``CAL`` switch |  Calibration data  |
+----------------+--------------------+
|                | 13 bytes per entry |
+----------------+--------------------+


The calibration data consists of 19 entries, that have 11 bytes (22 nibbles) of data and 2 bytes for checksum:

+--------------------------+
|       Calram entry       |
+--------+------+----------+
|   0:5  | 6:10 | 11:12    |
+========+======+==========+
| Offset | Gain | Checksum |
+--------+------+----------+

The offset is standard BCD 8421 encoded. The gain field is a little more complicated. The gain is stored as a 4-bit
two's complement signed number. Once decoded it gives the gain deviation from 1 in units of ppm. Finally the checksum
is ``0xFF`` minus the sum over the 11 data bytes. For implementation details check the source code of the
:mod:`hp3478a_async.hp_3478a_helper`.

The 19 calibration memory entries are the following functions:

=====  =============
Index  Function
=====  =============
0      30 mV DC
1      300 mV DC
2      3 V DC
3      30 V DC
4      300 V DC
5      Not used
6      V AC
7      30 Ω 2W/4W
8      300 Ω 2W/4W
9      3 kΩ 2W/4W
10     30 kΩ 2W/4W
11     300 kΩ 2W/4W
12     3 MΩ 2W/4W
13     30 MΩ 2W/4W
14     300 mA DC
15     3 A DC
16     Not used
17     300 mA/3 A AC
18     Not used
=====  =============

The device ignores the unused entries and does not complain about invalid data. Typically these entries are set to
``offset=0`` and ``gain=1.0``.
