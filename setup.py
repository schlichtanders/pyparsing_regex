#!/usr/bin/python
# -*- coding: utf-8 -*-
__author__ = 'Stephan Sahm'

import os
import shutil
from setuptools import setup
from distutils.command.clean import clean as Clean

# for compatibility with easy setup.py and pip install, we choose to use pyximport
# and hence do not compile cython extensions by setup.py:
# from Cython.Build import cythonize


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
    name='pyparsing_regex',
    version='0.1.0',
    description='Python regular expression interface like pyparsing',
    author=__author__,
    author_email='Stephan.Sahm@gmx.de',
    license='closed source',
    packages=['pyparsing_regex'],
    zip_safe=False,
    # ext_modules = cythonize("pyparsing_regex/_core_cython.pyx"),
    install_requires=["regex>=2016.1.10",
                      "pyparsing>=2.0.3",
                      "schlichtanders>=0.1.0"], # "schlichtanders @ git+https://github.com/schlichtanders/schlichtanders.git", # this is the future, however not yet implemented in setuptools
    extras_require={
        "pypy" : [],
        "cpython" : [ "cython>=0.23.4"],
    },
    # include_package_data=True,  # should work, but doesn't, I think pip does not recognize git automatically
    package_data = {
        'pyparsing_regex': ['*.pyx', '*pyxbld'], #include cython files
    },
    # This is the present, use "pip install --process-dependency-links -e ."
    dependency_links = ["git+https://github.com/schlichtanders/schlichtanders.git#egg=schlichtanders-0.1.0"],
    cmdclass={'clean': CleanCmd}
)