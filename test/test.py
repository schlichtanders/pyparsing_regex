#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import division
__author__ = 'Stephan Sahm <Stephan.Sahm@gmx.de>'

from pyparsing_regex import *
from schlichtanders.mywrappers import str_list

w = Word("abc", exact=2)
ww = w("a") + w("b")
r = Repeat(ww, 2, 4)

data = "abcbbccc"

print r.parseString(data)
print str_list(ww.searchString(data))
