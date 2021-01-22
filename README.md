# pyAsyncHP3478A
Python3 AsyncIO HP3478A driver. This library requires Python [asyncio](https://docs.python.org/3/library/asyncio.html) and AsyncIO library for the GPIB adapter. It also supports several undocuments functions for reading status registers and reading, modifying and writing the calibration memory.

## Supported GPIB Hardware
|Device|Supported|Tested|Comments|
|--|--|--|--|
|[AsyncIO Prologix GPIB library](https://github.com/PatrickBaus/pyAsyncPrologixGpib)|:heavy_check_mark:|:heavy_check_mark:|  |
|[AsyncIO linux-gpib wrapper](https://github.com/PatrickBaus/pyAsyncGpib)|:heavy_check_mark:|:heavy_check_mark:|  |

Tested using Linux, should work for Mac OSX, Windows and any OS with Python support.

## Setup
There are currently no packages available. To install the library, clone the repository into your project folder and install the required packages

```bash
python3 -m venv env  # virtual environment, optional
source env/bin/activate
pip install -r requirements.txt
# pip install -e ~/linux-gpib-code/linux-gpib-user/language/python/
```

## Usage
All examples assume, that the GPIB library is copied to the same root folder as the library. Either run
```bash
git clone https://github.com/PatrickBaus/pyAsyncPrologixGpib    # or alternativeliy
# git clone https://github.com/PatrickBaus/pyAsyncGpib
```
or download the source code from the git repository and copy it yourself.

A simple example for reading voltages.
```python
from pyAsyncHP3478A.HP_3478A import HP_3478A, FunctionType, TriggerType, Range

from pyAsyncPrologixGpib.pyAsyncPrologixGpib.pyAsyncPrologixGpib import AsyncPrologixGpibEthernetController, EosMode
from pyAsyncPrologixGpib.pyAsyncPrologixGpib.ip_connection import NotConnectedError, ConnectionLostError, NetworkError

# The default GPIB address is 27. The ip address of the prologix controller needs to changed.
ip_address = '127.0.0.1'
hp3478a = HP_3478A(connection=AsyncPrologixGpibEthernetController(ip_address, pad=27, timeout=1000, eos_mode=EosMode.APPEND_NONE))


# This example will print voltage data to the console
async def main():
    try: 
        # No need to explicitely bring up the GPIB connection. This will be done by the instrument.
        await hp3478a.connect()
        await asyncio.gather(
            hp3478a.set_function(FunctionType.DCV),      # Set to 4-wire ohm
            hp3478a.set_range(Range.RANGE_30),           # Set to 30 kOhm range
            hp3478a.set_trigger(TriggerType.INTERNAL),   # Enable free running trigger
            hp3478a.set_autozero(True),                  # Enable Autozero
            hp3478a.set_number_of_digits(6),             # Set the resolution to 5.5 digits
            hp3478a.connection.timeout(700),             # The maximum reading rate @ 50 Hz line freq. is 1.9 rds/s
        )

        # Take the measurements until Ctrl+C is pressed
        while 'loop not canceled':
            print(await hp3478a.read())

    except (ConnectionError, ConnectionRefusedError, NetworkError):
        logging.getLogger(__name__).error('Could not connect to remote target. Connection refused. Is the device connected?')
    except NotConnectedError:
        logging.getLogger(__name__).error('Not connected. Did you call .connect()?')
    finally:
        # Disconnect from the instrument. We may safely call diconnect() on a non-connected device, even
        # in case of a connection error
        await hp3478a.disconnect()

try:
    asyncio.run(main(), debug=False)
except KeyboardInterrupt:
    # The loop will be canceled on a KeyboardInterrupt by the run() method, we just want to suppress the exception
    pass
```

See [examples/](examples/) for more working examples.

### Methods
```python
   async def get_id()
```
This function returns the label `HP3478A`

```python
   async def connect()
```
Connect to the GPIB device. This function must be called from the loop and does all the setup of the GPIB adapter and the instrument.

```python
   async def disconnect()
```
Disconnect from the instrument and clean up. This call will also automatically remove the local lockout if set.

```python
   async def read(length=None)
```
Read the instrument buffer.

___Arguments___
* `length` [int] : optional. The number of bytes to be read. If no length is given, read until the line terminator `\n`.

___Returns___
* [Decimal or Bytes] : If the return value is a number, it will be returned as a Decimal, otherwise as a bytestring

___Raises___
* Raises an `OverflowError` if the instrument input is overloaded, i.e. returns `+9.99999E+9`.

```python
   async def write(msg)
```
Write a bytestring to the instrument. This string will be written unaltered. Use with caution.

___Arguments___
* `value` [Bytes] : The raw bytestring to be written to the instrument.

```python
   async def set_trigger(value)
```
Choose the type of trigger used.

___Arguments___
* `value` [[TriggerType](#triggertype)] : See the manual for details on the supported triggers. Accepts the [TriggerType](#triggertype) enum detailed below.

```python
   async def set_display(value, text="")
```
Set a custom text on the front panel display.

___Arguments___
* `value` [[DisplayType](#displaytype)] : See the manual for details on the supported options. Accepts the [DisplayType](#displaytype) enum detailed below. If set to `DisplayType.NORMAL`, no text will be set.
* `text` [String] : optional. The text to be displayed. There is no need to terminate the string with `\r` or `\n`.

```python
   async def set_srq_mask(value)
```
Set the interrupt mask. This will determine, when the GPIB SRQ is triggered by the instrument. The `SrqMask.DATA_READY` flag is useful, when reading with long conversion times. See [examples/](examples/) for more details.

___Arguments___
* `value` [[SrqMask](#srqmask)] : See the manual for details on the supported options. Accepts one or more of the [SrqMask](#srqmask) flags detailed below.

```python
   async def serial_poll()
```
Serial poll the instrument. Use this in combination with the SRQ mask to determine, if the instrument triggered the SRQ and requests service.

___Returns___
* [[SerialPollFlags](#serialpollflags)] : See the manual for details on each flag.

```python
   async def get_front_rear_switch_position()
```
Get the selected inpunt. The instrument has front and rear inputs.

___Returns___
* [[FrontRearSwitchPosition](#frontrearswitchposition)] : The position of the the Front/Rear switch on the front panel.

```python
   async def set_function(value)
```
Set the instrument measurment mode.

___Arguments___
* `value` [[FunctionType](#functiontype)] : See the manual for details on the supported options. Accepts the [FunctionType](#functiontype) enum detailed below.

```python
   async def set_range(value)
```
Set the instrument measurement range.

___Arguments___
* `value` [[Range](#range)] : See the manual for details on the supported options. These depend on the selected mode. Accepts the [Range](#range) enum detailed below.

```python
   async def set_number_of_digits(value)
```
Set the number of digits returned by calling read(). This influences the conversion time. See the manual for details.

___Arguments___
* `value` [int] : A number in the range [4,6].

```python
   async def set_autozero(enable)
```
Enable or disable autozero in between readings.

___Arguments___
* `value` [bool] : True to enable autozero.

```python
   async def clear()
```
Clear the serial poll register.

```python
   async def reset()
```
Place the instrument in DCV, autorange, autozero, single trigger, 4.5 digits mode and erase any output stored in the buffers.

```python
   async def local()
```
Enable the front panel buttons, if they the instrument is in local lock out.

```python
   async def get_error_register()
```
Read and clear the error register. This is the result of the power on self-test.

___Returns___
* [[ErrorFlags](#errorflags)] : See the manual for details on each flag.

```python
   async def get_status()
```
An undocumented function. This function returns the status of the instrument. It contains the current measurement mode, range, number of digits, status flags, SRQ flags, error register and a dac value.

___Returns___
* [dict] : A dictionary containing: current measurement mode, range, number of digits, status flags, SRQ flags, error register and a dac value.

```python
   async def get_cal_ram()
```
An undocumented function. This will read the calibration memory. It can be used to backup your calram. See [examples/](examples/) for an example on how to read the memory and convert it to meaningful data.

___Returns___
* [Bytes] : A bytestring as stored in calibration memory.

```python
   async def set_cal_ram(data)
```
An undocumented function. Warning. This function will attempt to write to the calibration memory, if the front panel CAL switch is enabled.

___Arguments___
* [String or Bytes] : A string or bytestring to write to the calibration memory.

### Enums

#### TriggerType
```python
class TriggerType(Enum):
    INTERNAL = 1
    EXTERNAL = 2
    SINGLE   = 3
    HOLD     = 4
    FAST     = 5
```

#### DisplayType
```python
class DisplayType(Enum):
    NORMAL               = 1
    SHOW_TEXT            = 2
    SHOW_TEXT_AND_FREEZE = 3
```

#### FrontRearSwitchPosition
```python
class FrontRearSwitchPosition(Enum):
    REAR  = 0
    FRONT = 1
```

#### FunctionType
```python
class FunctionType(Enum):
    DCV     = 1
    ACV     = 2
    OHM     = 3
    OHMF    = 4
    DCI     = 5
    ACI     = 6
    OHM_EXT = 7
```

#### Range
```python
class Range(Enum):
    RANGE_30M   = -2
    RANGE_300M  = -1
    RANGE_3     = 0
    RANGE_30    = 1
    RANGE_300   = 2
    RANGE_3k    = 3
    RANGE_30k   = 4
    RANGE_300k  = 5
    RANGE_3MEG  = 6
    RANGE_30MEG = 7
    RANGE_AUTO  = "A"
```

### Flags

#### SrqMask
```python
class SrqMask(Flag):
    NONE                = 0b0
    DATA_READY          = 0b1
    SYNTAX_ERROR        = 0b100
    HARDWARE_ERROR      = 0b1000
    FRONT_PANEL_SRQ     = 0b10000
    CALIBRATION_FAILURE = 0b100000
```

#### SerialPollFlags
```python
class SerialPollFlags(Flag):
    NONE                  = 0b0
    SRQ_ON_READING        = 0b1
    SRQ_ON_SYNTAX_ERROR   = 0b10
    SRQ_ON_HARDWARE_ERROR = 0b100
    SRQ_ON_SRQ_BUTTON     = 0b1000
    SRQ_ON_CAL_FAILURE    = 0b10000
    SRQ_ON_POWER_ON       = 0b1000000
```

#### ErrorFlags
```python
class ErrorFlags(Flag):
    NONE                 = 0b0
    CAL_RAM_CHECKSUM     = 0b1
    RAM_FAILURE          = 0b10
    ROM_FAILURE          = 0b100
    AD_SLOPE_CONVERGENCE = 0b1000
    AD_SELFTEST_FAILURE  = 0b10000
    AD_LINK_FAILURE      = 0b100000
```

## Calibration Memory
Using the `get_cal_ram()` function returns a bytestring, which can be converted using the helper functions provided
```python
from pyAsyncHP3478A.HP_3478A_helper import decode_cal_data

result = await hp3478a.get_cal_ram()
is_cal_enabled, data = decode_cal_data(result)
```
This helper will return a list of dictionaries, one for each calibration range.
|Index|Function|
|--|--|
|0|30 mV DC|
|1|300 mV DC|
|3|3 V DC|
|4|30 V DC|
|5|300 V DC|
|6|Not used|
|7|V AC|
|8|30 Ω 2W/4W|
|9|300 Ω 2W/4W|
|10|3 kΩ 2W/4W|
|11|30 kΩ 2W/4W|
|12|300 kΩ 2W/4W|
|13|3 MΩ 2W/4W|
|14|30 MΩ 2W/4W|
|15|300 mA DC|
|16|3 A DC|
|17|Not used|
|18|300 mA/3 A AC|
|19|Not used|

Each dictionary contains the following entries: `offset`, `gain`, `checksum` and `is_valid`. The checksum is `0xFF` minus the sum over the 11 data bytes. And the `is_valid` flag is boolean which is true, if the checksum matches.

The `encode_cal_data(data_blocks, cal_enable)` function takes a list with 19 dicts like above. In this case the dict may only contain the `offset` and `gain` all other values will be ignored. The checksum will be calculated by the function. The `cal_enable` boolean must be set to enable writing to the calibration memory.

The unused indices may not contain valid data. The instrument will not complain. Typically these are set to `offset=0` and `gain=1.0`.

## Thanks

Special thanks goes to [fenugrec](https://github.com/fenugrec/hp3478a_utils) and [Steve Matos](https://github.com/steve1515/hp3478a-calibration) for their work on deciphering the calram function.

## Versioning

I use [SemVer](http://semver.org/) for versioning. For the versions available, see the [tags on this repository](https://github.com/PatrickBaus/pyAsyncHP3478A/tags).

## Authors

* **Patrick Baus** - *Initial work* - [PatrickBaus](https://github.com/PatrickBaus)

## License


This project is licensed under the GPL v3 license - see the [LICENSE](LICENSE) file for details

