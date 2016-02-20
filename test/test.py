#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import division
__author__ = 'Stephan Sahm <Stephan.Sahm@gmx.de>'

from pyparsing_regex import *
from schlichtanders.mywrappers import str_list

w = Word("abc", exact=2)
#w = Regex("[abc]{2}")
ww = Group(w("a") + w("b"))
ww2 = GroupLiftKeys(ww + ww)("ww2")
r = Repeat(ww, 2, 4)
r2 = Repeat(ww2, 2, 4)

data = "abcbbcccabccbcca"

r_result = r.parseString(data)
print r_result
r2_result = r2.parseString(data)
print r2_result

ww_result = ww.searchString(data)
print str_list(ww_result)

# everything works as expected