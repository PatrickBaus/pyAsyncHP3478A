Examples
========
The HP 3478A requires a GPIB connection and a supported driver. This can be either one the drivers
supported by `Linux Gpib <https://linux-gpib.sourceforge.io/doc_html/supported-hardware.html>`_ or a
`Prologix Ethernet adapter <http://prologix.biz/gpib-ethernet-controller.html>`_.

The drivers can be found here:

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
