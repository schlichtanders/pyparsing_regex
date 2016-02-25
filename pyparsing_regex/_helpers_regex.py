# cython: profile=True
import regex
from itertools import izip

begins_suppressed = regex.compile(r"\(\?:") #TODO rename to begins_silently_grouped ?
begins_named = regex.compile(r"\(\?P<([^>]*)>")
#begins_named2 = regex.compile(r"\(\?<([^>]*)>")
begins_grouped = regex.compile(r"\(")
ends_grouped = regex.compile(r"(?r)\)") #reversed search feature (?r)    

begins_not_silently_grouped = regex.compile(r"\((?!\?)")

singleton_group = regex.compile(r"^\([^()]*\)$")

def group(pattern):
    return "(%s)" % pattern

def silent_group(pattern):
    return "(?:%s)" % pattern

def ensure_grouping(pattern, begins=begins_grouped, newgroup=silent_group):
    """ check whether starting ( corresponds to )
    if not add additional silent parentheses """

    if begins.match(pattern) and ends_grouped.match(pattern):
        # correspond last ) and initial ( ? then it is already grouped
        if list(closing_parentheses_match(pattern))[-1] == 0:
            return pattern

    return newgroup(pattern)

def closing_parentheses_match(data):
    openings = []
    for i, d in enumerate(data):
        if d=="(":
            openings.append(i)
        if d==")":
            yield openings.pop()

def decodeflags(flags, flags_sorted_bin = (None, "i", "L", "m", "s", "u", "x")):
    return "".join(d for d, s in izip(flags_sorted_bin, bin(flags)[-1:1:-1]) if s=='1')