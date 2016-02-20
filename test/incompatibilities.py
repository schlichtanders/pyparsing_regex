#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function, division

__author__ = 'Stephan Sahm <Stephan.Sahm@gmx.de>'


# Incompatibility with listAllMatches=True
# ----------------------------------------
import pyparsing as pp

g = pp.Group(pp.Word("ab", exact=2) + pp.Word("cd", exact=2))
gn = g.setResultsName("name", listAllMatches=True)
ogn = pp.OneOrMore(gn)


# this should be the same format I would guess, but it isn't
# the first one is flattened (or no additional level is added by default,
# don't know what is going on in the background)
print(gn.parseString("abcd")['name'][0])
print(ogn.parseString("abcdabcd")['name'][0])
# BUG in pyparsing ?
# !!!!!!!!!!!!!!!!!!

# pyparsing-regex inserts a new level here, always. So this is an incompatibility


