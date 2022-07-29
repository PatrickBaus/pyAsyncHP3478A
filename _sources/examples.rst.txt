Examples
========
The HP 3478A requires a GPIB connection and a supported driver. Currently two drivers are supported by the HP 3478A
driver: `Linux Gpib <https://linux-gpib.sourceforge.io>`_ or
`Prologix Ethernet adapter <http://prologix.biz/gpib-ethernet-controller.html>`_. Linux GPIB supports
`several <https://linux-gpib.sourceforge.io/doc_html/supported-hardware.html>`_
different hardware solutions.

The Python asyncio drivers can be found here:

* `Linux Gpib Wrapper <https://github.com/PatrickBaus/pyAsyncGpib>`_
* `Prologix asyncio driver <https://github.com/PatrickBaus/pyAsyncPrologixGpib>`_

See the basic example below for an implementation using the Prologix driver:

Basic Example
-------------

.. literalinclude:: ../../examples/simple.py
    :language: python

More Examples
-------------
More examples can be found in the
`examples folder <https://github.com/PatrickBaus/pyAsyncHP3478A/tree/master/examples/>`_.
