#!/usr/bin/env python

import io
import os

from setuptools import setup


def readme():
    with io.open(os.path.join(os.path.dirname(__file__), 'README.rst'), mode="r", encoding="UTF-8") as readmef:
        return readmef.read()


setup(name='picast',
      version='0.1',
      description='A simple wireless display receiver/sink for Raspberry Pi',
      url='http://github.com/miurahr/picast',
      license='GPL3',
      long_description=readme(),
      author='Hioshi Miura',
      author_email='miurahr@linux.com',
      requires=['PyGObject'],
      classifiers=[
          'Development Status :: 2 - Pre-Alpha',
          'Environment :: X11 Applications',
          'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
          'Operating System :: POSIX :: Linux',
          'Programming Language :: Python',
          'Topic :: Utilities',
      ],
      )
