# Pyparsing-like Interface
# ========================
try:
    import pyximport; pyximport.install()
    from pyparsing_regex._core2 import ParserElement, Structure
except ImportError:
    from pyparsing_regex._core import ParserElement, Structure

import pyparsing_regex._helpers_regex as hre
import regex
import __builtin__
from copy import copy

import cPickle

def deepcopy(o):
    """fast deepcopy alternative"""
    return cPickle.loads(cPickle.dumps(o, -1))

# emulate generic methods from pyparsing itself:
from pyparsing import srange




class Literal(ParserElement):
    def __init__(self, str):
        super(Literal, self).__init__(regex.escape(str))

class Regex(ParserElement):
    def __init__(self, pattern, flags=0):
        """flags are locally scoped and will only effect the supplied pattern, nothing more"""
        if flags:
            str_flags = hre.decodeflags(flags)
            pattern = r"(?%s:%s)"%(str_flags, pattern)
        super(Regex, self).__init__(pattern)


class Word(ParserElement):
    def __init__(self, initChars, bodyChars=None, min=1, max=0, exact=0, excludeChars=None):
        """not implemented kwargs: asKeyword """
        if max != 0 and min > max:
            raise RuntimeError("min <= max needed")

        if excludeChars:
            initChars = initChars + "--" + excludeChars
            if bodyChars:
                bodyChars = bodyChars + "--" + excludeChars

        if exact == 1 or max == 1:
            pattern = r"[%s]{1}"%(initChars)
        elif exact > 1:
            if bodyChars:
                pattern = r"[%s]{1}[%s]{%s}"%(initChars, bodyChars, exact-1)
            else:
                pattern = r"[%s]{%s}"%(initChars, exact)
        elif max > 1:
            if bodyChars:
                pattern = r"[%s]{1}[%s]{%s,%s}"%(initChars, bodyChars, __builtin__.max(min-1,0), max-1)
            else:
                pattern = r"[%s]{%s,%s}"%(initChars, min, max)
        else: # arbitrary upper bound
            if bodyChars:
                pattern = r"[%s]{1}[%s]{%s,}"%(initChars, bodyChars, __builtin__.max(min-1,0))
            else:
                pattern = r"[%s]{%s,}"%(initChars, min)
        super(Word, self).__init__(pattern)

class CharsNotIn(Word):
    def __init__(self, notChars, min=1, max=0, exact=0):
        super(CharsNotIn, self).__init__("^%s" % notChars, min=min, max=max, exact=exact)


def _silent_pattern(expr):
    if isinstance(expr, basestring):
        return regex.escape(expr)
    else:
        return hre.begins_not_silently_grouped.sub("(?:", expr.pattern)

class SkipTo(ParserElement):
    def __init__(self, expr, include_=False):
        """Grouped by default. not supported: ignore=None, failOn=None.

        Token for skipping over all undefined text until the matched expression is found.
        If C{include} is set to true, the matched expression is also parsed (the skipped text
        and matched expression are returned as a 2-element list).  The C{ignore}
        argument is used to define grammars (typically quoted strings and comments) that
        might contain false matches.
        """
        pattern = r"(?:.(?!%s))*." % _silent_pattern(expr)
        if include_:
            pattern += _silent_pattern(expr)
        super(SkipTo, self).__init__(pattern)


class FollowedBy(ParserElement):
    def __init__(self, expr):
        """Lookahead matching of the given parse expression.  C{FollowedBy}
        does *not* advance the parsing position within the input string, it only
        verifies that the specified parse expression matches at the current
        position.  C{FollowedBy} always returns a null token list."""
        pattern = r"(?=%s)" % _silent_pattern(expr) # standard lookahead
        super(FollowedBy, self).__init__(pattern, silent=True)

class Combine(ParserElement):
    def __init__(self, expr):
        """Converter to concatenate all matching tokens to a single string.
        By default, the matching patterns must also be contiguous in the input string;
        this can be disabled by specifying C{'adjacent=False'} in the constructor."""
        super(Combine, self).__init__(_silent_pattern(expr))


class Suppress(ParserElement):
    def __init__(self, expr):
        super(Suppress, self).__init__(_silent_pattern(expr), silent=True)


class StringStart(ParserElement):
    def __init__(self):
        """matches beginning of the text"""
        super(StringStart, self).__init__(r"^")

class StringEnd(ParserElement):
    def __init__(self):
        """matches the end of the text"""
        super(StringEnd, self).__init__(r"$")

class LineStart(Regex):
    def __init__(self):
        """matches beginning of a line (lines delimited by \n characters)"""
        super(LineStart, self).__init__(r"^", regex.MULTILINE)

class LineEnd(Regex):
    def __init__(self):
        """matches the end of a line"""
        super(LineEnd, self).__init__(r"$", regex.MULTILINE)


# For the rest, functions are much easier than classes, so we keep it with them

def And(iterable):
    """__dict__ of first element will be passed through And result """
    try:
        gen = iter(iterable)
        first = next(gen)
        first.__class__ = ParserElement
        base = first + next(gen) # once (+) to have a new element
        for expr in gen:
            base += expr  # in place addition to avoid copying
        return base
    except StopIteration:  # only one element
        return first


def MatchFirst(iterable):
    """__dict__ of first element will be passed through MatchFirst result """
    try:
        gen = iter(iterable)
        first = next(gen)
        first.__class__ = ParserElement
        base = first | next(gen) # once (|) to have a new element
        for expr in gen:
            base |= expr  # in place or to avoid copying
        return base
    except StopIteration:  # only one element
        return first

#Or __xor__ and Each __and__ are missing - takes more time to implement

def Optional(expr, default=None):
    if default is not None:
        Structure.EMPTY_DEFAULT = default
    cp = copy(expr)
    cp.__class__ = ParserElement
    cp.pattern = r"%s?" % hre.ensure_grouping(cp.pattern)
    return cp

def Group(expr):
    g = deepcopy(expr)
    g.__class__ = ParserElement
    g.group(silent=True)
    return g

def GroupLiftKeys(expr):
    g = deepcopy(expr)
    g.__class__ = ParserElement
    g.group(silent=True, liftkeys=True)
    return g

def OneOrMore(expr):
    return Repeat(expr, min=1)

def ZeroOrMore(expr):
    return Repeat(expr)

def Repeat(expr, min=0, max=None):
    expr = deepcopy(expr)
    expr.__class__ = ParserElement
    expr.repeat(min=min, max=max)
    return expr





# my own extras:
# ==============

def setResultsNameInPlace(expr, name, listAllMatches=False):
    """ adds resultsname in place, no copy as with method

    :param expr: parser to set resultsname
    :param name: resultsname
    :param listAllMatches: whether strings matches should all be listed, or only last match should be kept
    """
    expr.setResultsName(name)
    return expr