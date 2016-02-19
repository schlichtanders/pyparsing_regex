#!/usr/bin/python
# -*- coding: utf-8 -*-
__author__ = 'Stephan Sahm'

import os
import shutil
from setuptools import setup
from distutils.command.clean import clean as Clean

# TODO profile with new profiler
# TODO compare performance with Fabians old version


class CleanCmd(Clean):

    description = "Cleans ..."

    def run(self):

        Clean.run(self)

        if os.path.exists('build'):
            shutil.rmtree('build')

        for dirpath, dirnames, filenames in os.walk('.'):
            for filename in filenames:
                if (filename.endswith('.so') or
                    filename.endswith('.pyd') or
                    filename.endswith('.pyc') or
                    filename.endswith('_wrap.c') or
                    filename.startswith('wrapper_') or
                    filename.endswith('~')):
                        os.unlink(os.path.join(dirpath, filename))

            for dirname in dirnames:
                if dirname == '__pycache__' or dirname == 'build':
                    shutil.rmtree(os.path.join(dirpath, dirname))
                if dirname == "pymscons.egg-info":
                    shutil.rmtree(os.path.join(dirpath, dirname))

setup(
    name='pyparsing-regex',
    version='0.1',
    description='Python regular expression interface like pyparsing',
    author=__author__,
    author_email='Stephan.Sahm@gmx.de',
    license='closed source',
    packages=['pyparsing_regex'],
    zip_safe=False,
    install_requires=["overrides>=0.5",
                      "wrapt>=1.10.6",
                      "regex>=2016.01.10",
                      "pyparsing>=2.0.3"],
    # TODO add package schlichtanders
    cmdclass={'clean': CleanCmd}
    )
