from setuptools import setup
from hp3478a_async import VERSION

with open('README.md', 'r') as f:
    long_description = f.read()

setup(
   name='hp3478a_async',
   version=VERSION,
   author='Patrick Baus',
   author_email='patrick.baus@physik.tu-darmstadt.de',
   url='https://github.com/PatrickBaus/pyAsyncHP3478A',
   description='An AsyncIO driver for the HP 3478A digital multimeter',
   long_description=long_description,
   classifiers=[
    'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
    'Programming Language :: Python',
    'Development Status :: 4 - Beta',
    'Intended Audience :: Developers',
    'Natural Language :: English',
    'Topic :: Interface Engine/Protocol Translator',
   ],
   keywords='GPIB ',
   license='GPL',
   license_files=('LICENSE',),
   packages=['hp3478a_async'],  # same as name
   install_requires=[],  # external packages as dependencies
)
