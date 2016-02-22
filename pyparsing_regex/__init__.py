import __builtin__
import regex
import sys
import itertools as it
from copy import copy
import abc
from collections import namedtuple
from overrides import overrides
from functools import partial

from schlichtanders.myobjects import Count, Leaf, Structure, FastStructure
from schlichtanders.mygenerators import hist
import helpers_regex as hre
from pprint import pformat

import cPickle
import ujson

serializer = ujson

def deepcopy(o):
    """fast deepcopy alternative"""
    return cPickle.loads(cPickle.dumps(o, -1))

# emulate generic methods from pyparsing itself:
from pyparsing import srange

_MAX_INT = sys.maxint

# parser specific definitions
# ===========================

class ParserElementType(object):
    """ abstract class capturing the interface of an arbitrary ParserElement of pyparsing """
    __metaclass__ = abc.ABCMeta

    def __call__(self, name, **kwargs):
        return deepcopy(self).setResultsName(name, **kwargs)

    @abc.abstractmethod
    def setResultsName(self, name, **kwargs):
        """ kwargs are for compatibility with pyparsing interface """
        return self

    def setName(self, name):
        """ this is not yet implemented, so no easier output yet
        :param name:
        :return:
        """
        return self

    @abc.abstractmethod
    def suppress(self):
        """Suppresses the output of this C{ParserElement}; useful to keep punctuation from
           cluttering up returned output.

           change outer brackets, e.g. (...) or (?P<>...) or (?<>...) to non-capturing (?:...) version
        """
        return self

    @abc.abstractmethod
    def repeat(self, min=0, max=None):
        """ repititions is the main structural addition on top of the Structure-type """
        raise NotImplemented()

    def parseString(self, instring, parseAll=False):
        """Execute the parse expression with the given string.
        This is the main interface to the client code, once the complete
        expression has been built.

        If you want the grammar to require that the entire input string be
        successfully parsed, then set C{parseAll} to True (equivalent to ending
        the grammar with C{L{StringEnd()}}).

        Note: C{parseString} implicitly calls C{expandtabs()} on the input string,
        in order to report proper column numbers in parse actions.
        If the input string contains tabs and
        the grammar uses parse actions that use the C{loc} argument to index into the
        string being parsed, you can ensure you have a consistent view of the input
        string by:
        - calling C{parseWithTabs} on your grammar before calling C{parseString}
          (see L{I{parseWithTabs}<parseWithTabs>})
        - define your parse action using the full C{(s,loc,toks)} signature, and
          reference the input string using the parse action's C{s} argument
        - explictly expand the tabs in your input string before calling
          C{parseString}

        Return ParseResult!
        """
        return (self+StringEnd() if parseAll else self)._parseString(instring)

    @abc.abstractmethod
    def _parseString(self, instring):
        raise NotImplemented()


    def scanString(self, instring, maxMatches=_MAX_INT, overlap=False):
        """not supported: maxMatches

        Scan the input string for expression matches.  Each match will return the
        matching tokens, start location, and end location.  May be called with optional
        C{maxMatches} argument, to clip scanning after 'n' matches are found.  If
        C{overlap} is specified, then overlapping matches will be reported.

        Note that the start and end locations are reported relative to the string
        being parsed.  See L{I{parseString}<parseString>} for more information on parsing
        strings with embedded tabs.
        """
        i = 0
        matches = 0
        while i < len(instring) and matches < maxMatches:
            m = self.parseString(instring[i:])
            if m is not None:
                yield m
                matches += 1
                if overlap:
                    i += 1
                else:
                    i += m.parse_end
            else:
                i += 1


    def transformString(self, instring):
        raise NotImplementedError("with regular expressions setParseAction is not supported and thus also not transformString")
        #maybe later by using regex substitution

    def searchString(self, instring, maxMatches=_MAX_INT):
        """Another extension to C{L{scanString}}, simplifying the access to the tokens found
           to match the given parse expression.  May be called with optional
           C{maxMatches} argument, to clip searching after 'n' matches are found.
        """
        return list(self.scanString(instring))

    def __add__(self, other):
        base = deepcopy(self)
        base += other # (+=) == __iadd__
        return base

    @abc.abstractmethod
    def __iadd__(self, other):
        raise NotImplemented()

    def __or__(self, other):
        base = deepcopy(self)
        base |= other # (|=) == __ior__
        return base

    @abc.abstractmethod
    def __ior__(self, other):
        raise NotImplemented()

    def pprint(self):
        """not implemented in more detail"""
        return pformat(repr(self))


#: small helper classes for substructuring:
class Repeated(object):
    def __init__(self, count, struct):
        self.count = count
        self.struct = struct

class MatchedGroup(object):
    def __init__(self, ends, captures=None):
        self.ends = ends
        self.captures = captures

    def __str__(self):
        return "{ends: %s, captures: %s}" % (self.ends, self.captures)
    def __repr__(self):
        return str(self)

# TODO probably not needed after refactoring:
def recursive_structure_delift(struct):
    """ more complex delift for struct types, as the struct type itself is usually nested """
    struct.__class__ = Structure
    for s in struct.iter_nopseudo(): # flattens out Leafs
        if isinstance(s, Structure):
            recursive_structure_delift(s)
        elif isinstance(s, Repeated):
            recursive_structure_delift(s.struct)


class ParserElement(ParserElementType):
    """
    we can immitate arbitrarily complex formula directly by a single regex-string
    the output gets restructured (in linear time) to fulfil ParserElement/Structure interface

    not implemented: whitespaces support
    """


    # CONSTRUCTION
    # ============

    def __init__(self, pattern, silent=False):
        if silent:
            # create empty Structure:
            self.struct = FastStructure()
            self.pattern = pattern
            self.name = self.pattern
        else:
            # create Count() Structure
            self.struct = FastStructure(Count())
            self.pattern = hre.group(pattern)  # for every Count() there must be a group
            self.name = self.pattern
        self._compiled = None

    # LOGIC
    # =====

    def group(self, wrapper=lambda x:x, pseudo=False, liftkeys=False, silent=None):
        # this is inplace:
        self.struct.group(wrapper, pseudo=pseudo, liftkeys=liftkeys)
        # normal grouping is done by Structure type,
        # but silent groups are nevertheless needed for correct regex semantics:
        if silent is None:
            pass # keep old self.pattern, this is mainly needed for pseudo groups like created for ResultNames
        elif silent:
            self.pattern = hre.ensure_grouping(self.pattern)
        else:
            self.pattern = hre.group(self.pattern)
        self._compiled = None
        return

    def setResultsName(self, name, **kwargs):
        """ kwargs are for compatibility with pyparsing interface """
        self.struct.set_name(name)
        return self

    def setName(self, name):
        self.name = name
        return self

    def suppress(self):
        """Suppresses the output of this C{ParserElement}; useful to keep punctuation from
           cluttering up returned output.

           change all inner brackets, e.g. (...) or (?P<>...) or (?<>...) to non-capturing (?:...) version

           CAUTION: NOT REVERSIBLE!
        """
        self.pattern = hre.begins_not_silently_grouped.sub("(?:", self.pattern)
        self._compiled = None
        self.struct.clear()
        return self

    def repeat(self, min=0, max=None):
        """ repeat on arbitrary ParserElement """
        if max is not None and min > max:
            raise RuntimeError("min <= max needed")

        # if there is at most one real group in the pattern,
        # then there is no structure so far at all
        # and thus we do not have to group, but just can repeat
        # (mind by .suppress() there may also be zero real groups, which also don't have to be grouped)
        # additionally, there is also no need for a further nesting if the sub group was just repeated

        if (len(hre.begins_not_silently_grouped.findall(self.pattern)) <= 1
            or (isinstance(self.struct[0], Repeated) and len(self.struct)==1)):
            # we still need to group silently so to not break anything
            # (otherwise e.g. UNH...'{1, 99} appears, which instead of repeating the "group", just will repeat the last element)
            self.pattern = hre.ensure_grouping(self.pattern)
        else:
            # the grouping is done by wrapping into a Leaf,
            # so that we can construct a map function which does all restructuring of the regex output
            self.group(
                # wrapper = lambda struct: Leaf(Repeated(Count(), struct)), #Structure version
                wrapper = lambda struct: Repeated(Count(), struct), #FastStructure version
                pseudo = True, # pass everything through
                liftkeys = True, # pass everything through
                silent = False, # this adds a grouping level also in the pattern
            )
        if max is None:
            self.pattern = r"%s{%s,}"   % (self.pattern, min)
        elif min == max:
            self.pattern = r"%s{%s}"    % (self.pattern, min)
        else:
            self.pattern = r"%s{%s,%s}" % (self.pattern, min, max)
        self._compiled = None

    def compile(self):
        # compile regex (should optimize itself)
        self._compiled = regex.compile(self.pattern)

        return self._compiled

    def _parseString(self, instring):
        """starts matchin at starts of ``instring`` - no search

        this is copying everything beforehand"""

        if self._compiled is None:
            self.compile()

        match = self._compiled.match(instring)
        if match is None:
            return None

        Count.reset()
        struct = deepcopy(self.struct) # TODO this might get faster by using json serialization

        mymatch, substruct_dumped, preprocess_func = self._parse_preprocess(match)
        struct.map(preprocess_func)
        struct.map(self._func_parse_leaf(mymatch, substruct_dumped))
        struct.parse_end = match.end()
        return struct

    @staticmethod
    def _parse_preprocess(match):
        """ evals Counts, transforms match, and dumps structures for repititions

        attention! returns function as second, and match_transformed as first argument,
        however this match_transformed is still empty initially and will be set by running the
        function

        :param match: to be transformed
        :return: match_transformed, evalcount_func
        """
        match_transformed = []
        substructs_dumped = {} #{Count: dumps(substruct)}
        def preprocess_func(leaf):
            """ evaluates all Count instances so that they refer to fixed group """
            if isinstance(leaf, Repeated):
                new_leaf = leaf.count.value # evaluates and stores value directly
                # CAUTION: +1 as we now start counting at 0
                match_transformed.append(MatchedGroup(match.ends(new_leaf + 1)))
                # recursive call
                # leaf.struct.map(preprocess_func) # Structure version
                FastStructure._map(leaf.struct, preprocess_func) # FastStructure version
                # from here on everything is executed depth first (by recursion)
                substructs_dumped[new_leaf] = serializer.dumps(leaf.struct)

            # elif isinstance(leaf, Count):
            else: #there should be no other case
                new_leaf = leaf.value # evaluates and stores value directly
                # CAUTION: +1 as we now start counting at 0
                match_transformed.append(MatchedGroup(match.ends(new_leaf + 1), match.captures(new_leaf + 1)))

            return new_leaf # new_leaf is int

        return match_transformed, substructs_dumped, preprocess_func

    @staticmethod
    def _func_parse_leaf(mymatch, substruct_dumped):
        """
        CAUTION: for this map to work correctly,
        every Count instance must be evaluated and directly available (recursively!)
        i.e. first map ParserElement._recursive_evalcount
        """
        def recursive_parse(leaf, maxend=None):
            try: # Repeated structure
                dumped = substruct_dumped[leaf]
                def gen():
                    if maxend is None:
                        for end in mymatch[leaf].ends:
                            yield FastStructure._map(  # FastStructure version, works directly with dicts
                            serializer.loads(dumped),
                            partial(recursive_parse, maxend=end)
                        )
                    else:
                        for i, end in enumerate(mymatch[leaf].ends):
                            if end > maxend:
                                del mymatch[leaf].ends[:i] #delete everything parsed so far
                                # captures are of no interest at all of these Repeated elements
                                break
                            # yield deepcopy(leaf.struct).map(partial(recursive_parse, maxend=end)) # naive version
                            # yield serializer.loads(dumped).map(partial(recursive_parse, maxend=end)) # Structure version
                            yield FastStructure._map(  # FastStructure version, works directly with dicts
                                serializer.loads(dumped),
                                partial(recursive_parse, maxend=end)
                            )

                # returns structure which is labeld pseudo by initial repeat method
                # return reduce(op.add, gen())

                # alternatively return simple list, which is flattened out automatically
                # (same effect as pseudo structure, however one could process this repetitions further,
                # e.g. keeping only last repition like it is done in pyparsing for default)
                ret = list(gen())
                return ret

            except KeyError: # base case:
                if maxend is None:
                    ret = mymatch[leaf].captures[:]
                    del mymatch[leaf].captures[:]
                    del mymatch[leaf].ends[:]
                else:
                    i = -1
                    for i, end in enumerate(mymatch[leaf].ends):
                        if end > maxend:
                            # i is now the final valid index+1
                            break
                    else:
                        # no break, i.e. we currently miss the last one, OR empty loop
                        i += 1 # if nothing was done, i=0 now, giving empty list and no deletes

                    ret = mymatch[leaf].captures[:i]
                    # delete everything parsed so far (both captures end ends!):
                    del mymatch[leaf].captures[:i]
                    del mymatch[leaf].ends[:i]
                return ret

        return recursive_parse

    def __iadd__(self, other):
        if isinstance(other, basestring):
            other = ParserElement(regex.escape(other))
        self.struct += other.struct
        self.pattern += other.pattern
        self.name += other.name
        self._compiled = None
        return self

    def __radd__(self, other):
        if isinstance(other, basestring):
            other = ParserElement(regex.escape(other))
        other += self #__iadd__
        return other

    def __ior__(self, other):
        # TODO I think there is some crucial error in this OR construction
        # related to fact, that in regex an additional or gets an additional Count,
        # however, such Counts getting empty because another branch was used, should
        # usually not appear in the output, but just get ommitted
        # - more booktracking needed
        if isinstance(other, basestring):
            other = ParserElement(regex.escape(other))

        self.struct += other.struct
        self.pattern += "|" + other.pattern
        self.name += "|" + other.name
        self.group(pseudo = True,
                   liftkeys = True,
                   silent = True)
        return self

    def __ror__(self, other):
        if isinstance(other, basestring):
            other = ParserElement(regex.escape(other))
        other |= self  #__ior__
        return other

    def __str__(self):
        # [] are for pprint, () would make more sense
        return "['%s', %s]" % (self.name, str(self.struct))

    def __repr__(self):
        # [] are for pprint, () would make more sense
        return "['%s', %s, r'%s']" % (self.name, repr(self.struct), self.pattern)




# Pyparsing-like Interface
# ========================

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
    def __init__(self, expr, include=False):
        """Grouped by default. not supported: ignore=None, failOn=None.

        Token for skipping over all undefined text until the matched expression is found.
        If C{include} is set to true, the matched expression is also parsed (the skipped text
        and matched expression are returned as a 2-element list).  The C{ignore}
        argument is used to define grammars (typically quoted strings and comments) that
        might contain false matches.
        """
        pattern = r"(?:.(?!%s))*." % _silent_pattern(expr)
        if include:
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
        base = next(gen) | next(gen) # once (|) to have a new element
        for expr in gen:
            base |= expr  # in place or to avoid copying
        return base
    except StopIteration:  # only one element
        return next(iter(iterable))

#Or __xor__ and Each __and__ are missing - takes more time to implement

def Optional(expr, default=None):
    if default is not None:
        Leaf.EMPTY_DEFAULT = default
    cp = copy(expr)
    cp.pattern = r"%s?" % hre.ensure_grouping(cp.pattern)
    return cp

def Group(expr):
    g = deepcopy(expr)
    g.group(silent=True)
    return g

def GroupLiftKeys(expr):
    g = deepcopy(expr)
    g.group(silent=True, liftkeys=True)
    return g

def OneOrMore(expr):
    return Repeat(expr, min=1)

def ZeroOrMore(expr):
    return Repeat(expr)

def Repeat(expr, min=0, max=None):
    expr = deepcopy(expr)
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