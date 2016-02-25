pyparsing_regex
===============

This package is a pyparsing implementation for *non-recursive* structures.
It is meant to provide the same generic interface as well as output.

The crucial advantage: it is faster.
Further it uses regex at the ground, so that for maximal speed, with no fancy output-support needed,
the regex-pattern can just be asked for and matched individually.


Install
=======

Use pip with additioanl dependencies support.

    pip install --process-dependency-links "git+https://github.com/schlichtanders/pyparsing_regex.git#egg=pyparsing_regex"

To install CPython dependencies (not runnable within PyPy) use

    pip install --process-dependency-links "git+https://github.com/schlichtanders/pyparsing_regex.git#egg=pyparsing_regex[CPython]"

For a local development install, first clone the git repository, and then e.g. for the CPython version:

    pip install --process-dependency-links -e "file:///user/filetogitclone/pyparsing_regex#egg=pyparsing_regex[CPython]"


Features
========

Supported PyParsing Elements
----------------------------

- And constructions
- Optional
- SkipTo
- Suppress
- Word
- Regex
- Group
- OneOrMore
- ZeroOrMore


Additional Features
-------------------

- GroupLiftKeys
- Repeated


Not Yet Supported PyParsing
---------------------------

- setParseAction
- there might be issues with OR constructions (not tested
- Whitespace support
- ...