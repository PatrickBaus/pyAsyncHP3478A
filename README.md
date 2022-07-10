[![pylint](https://github.com/PatrickBaus/pyAsyncHP3478A/actions/workflows/pylint.yml/badge.svg)](https://github.com/PatrickBaus/pyAsyncHP3478A/actions/workflows/pylint.yml)
[![PyPI](https://img.shields.io/pypi/v/hp3478a_async)](https://pypi.org/project/hp3478a_async/)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/hp3478a_async)
![PyPI - Status](https://img.shields.io/pypi/status/hp3478a_async)
[![code style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
# hp3478a_async
Python3 AsyncIO HP3478A driver. This library requires Python
[asyncio](https://docs.python.org/3/library/asyncio.html) and AsyncIO library for the GPIB adapter. It also supports
several undocumented functions for reading status registers and reading, modifying and writing the calibration memory.

The library is fully type-hinted.

## Supported GPIB Hardware
|Device|Supported|Tested|Comments|
|--|--|--|--|
|[AsyncIO Prologix GPIB library](https://github.com/PatrickBaus/pyAsyncPrologixGpib)|:heavy_check_mark:|:heavy_check_mark:|  |
|[AsyncIO linux-gpib wrapper](https://github.com/PatrickBaus/pyAsyncGpib)|:heavy_check_mark:|:heavy_check_mark:|  |

Tested using Linux, should work for Mac OSX, Windows and any OS with Python support.

## Documentation
The full documentation can be found on GitHub Pages:
[https://patrickbaus.github.io/pyAsyncHP3478A/](https://patrickbaus.github.io/pyAsyncHP3478A/). I use the
[Numpydoc](https://numpydoc.readthedocs.io/en/latest/format.html) style for documentation and
[Sphinx](https://www.sphinx-doc.org/en/master/index.html) for compiling it.

# Setup
To install the library in a virtual environment (always use venvs with every project):
```bash
python3 -m venv env  # virtual environment, optional
source env/bin/activate  # only if the virtual environment is used
pip install hp3478a-async
```

## Usage
All examples assume, that a GPIB library is installed as well. Either run
```bash
pip install prologix-gpib-async    # or alternatively
# pip install async-gpib
```
or download the source code from the git repository and copy it to the root folder yourself.

The library uses an asynchronous context manager to make cleanup easier. You can use either the
context manager syntax or invoke the calls manually:

```python
async with HP_3478A(connection=gpib_device) as hp3478a:
    # Add your code here
    ...
```

```python
try:
    hp3478a = HP_3478A(connection=gpib_device)
    await hp3478a.connect()
    # your code
finally:
    await hp3478a.disconnect()
```

A more complete example for reading voltages:
```python
import asyncio
import logging

from hp3478a_async import HP_3478A, FunctionType, TriggerType, Range

from pyAsyncPrologixGpib import AsyncPrologixGpibEthernetController, EosMode

# The default GPIB address is 27. The ip address of the prologix controller needs to be changed.
ip_address = "127.0.0.1"
gpib_device = AsyncPrologixGpibEthernetController(ip_address, pad=27, timeout=1000, eos_mode=EosMode.APPEND_NONE)


async def main():
    """This example will print voltage data to the console"""
    try:
        # No need to explicitly bring up the GPIB connection. This will be done by the instrument.
        async with HP_3478A(connection=gpib_device) as hp3478a:
            await asyncio.gather(
                hp3478a.set_function(FunctionType.DCV),  # Set to 4-wire ohm
                hp3478a.set_range(Range.RANGE_30),  # Set to 30 kOhm range
                hp3478a.set_trigger(TriggerType.INTERNAL),  # Enable free running trigger
                hp3478a.set_autozero(True),  # Enable Autozero
                hp3478a.set_number_of_digits(6),  # Set the resolution to 5.5 digits
                hp3478a.connection.timeout(700),  # The maximum reading rate @ 50 Hz line freq. is 1.9 rds/s
            )

            # Take the measurements until Ctrl+C is pressed
            async for result in hp3478a.read_all():
                print(result)
    except (ConnectionError, ConnectionRefusedError):
        logging.getLogger(__name__).error(
            "Could not connect to remote target. Connection refused. Is the device connected?"
        )


try:
    asyncio.run(main(), debug=False)
except KeyboardInterrupt:
    # The loop will be canceled on a KeyboardInterrupt by the run() method, we just want to suppress the exception
    pass
```

See [examples/](https://github.com/PatrickBaus/pyAsyncHP3478A/tree/master/examples/) for more working examples.

# Unit Tests
There are unit tests available for the calram encoder and decoder.
```bash
source env/bin/activate  # only if the virtual environment is used
pytest
```

## Thanks
Special thanks goes to [fenugrec](https://github.com/fenugrec/hp3478a_utils) and
[Steve Matos](https://github.com/steve1515/hp3478a-calibration) for their work on deciphering the calram function.

## Versioning
I use [SemVer](http://semver.org/) for versioning. For the versions available, see the
[tags on this repository](https://github.com/PatrickBaus/pyAsyncHP3478A/tags).

## Authors
* **Patrick Baus** - *Initial work* - [PatrickBaus](https://github.com/PatrickBaus)

## License
This project is licensed under the GPL v3 license - see the
[LICENSE](https://github.com/PatrickBaus/pyAsyncHP3478A/tree/master/LICENSE) file for details
