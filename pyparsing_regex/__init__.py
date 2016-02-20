import __builtin__
import regex
import sys
import itertools as it
from copy import copy, deepcopy
import abc
from collections import namedtuple
from overrides import overrides
from functools import partial
from wrapt import ObjectProxy

from schlichtanders.myobjects import Count, Leaf, Structure, recursive_structure_delift
import helpers_regex as hre
from pprint import pformat

# emulate generic methods from pyparsing itself:
from pyparsing import srange

_MAX_INT = sys.maxint

# parser specific definitions
# ===========================

class ParserElementType(Structure):
    """ abstract class capturing the interface of an arbitrary ParserElement of pyparsing """
    __metaclass__ = abc.ABCMeta
        
    def __call__(self, name, **kwargs):
        # TODO deepcopy needed?
        return deepcopy(self).setResultsName(name, **kwargs)
    
    def setResultsName(self, name, **kwargs):
        """ kwargs are for compatibility with pyparsing interface """
        self.set_name(name)
        return self # TODO is this the standard behaviour?

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
                    i += m.end()
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
    
    # add, iadd already defined in Structure
            
    def __or__(self, other):
        base = deepcopy(self)
        base |= other # (|=) == __iadd__
        return base
    
    @abc.abstractmethod
    def __ior__(self, other):
        raise NotImplemented()

    def pprint(self):
        """not implemented in more detail"""
        return pformat(repr(self))

        
        
class ParseResult(ObjectProxy):
    """ pseudo class, capturing interface of return type of pyparsing (and more needed methods) """

    def __init__(self, structure, span, flatten_singletons=None, empty_default="EMPTYLIST"):
        # proxy the complete structure element:
        super(ParseResult, self).__init__(structure)    
        # general information over ParseResult:
        self.span = span
        
    def end(self):
        "returns match end for given string"
        return self.span[1]
    
    def span(self):
        "returns (match begin, match end) for given string"
        return self.span

    
class ParserElement(ParserElementType):
    """   
    we can immitate arbitrarily complex formula directly by a single regex-string
    the output gets restructured (in linear time) to fulfil ParserElement/Structure interface
    
    not implemented: whitespaces support
    """
    
    #: repeated substructure (just a tuple)
    Repeated = namedtuple("Repeated", ["count", "struct"])
    MatchedGroup = namedtuple("Group", ["ends", "captures"])
    
    # CONSTRUCTION
    # ============

    def __init__(self, pattern, silent=False):
        if silent:
            # create empty Structure:
            super(ParserElement, self).__init__(_list=[])
            self.pattern = pattern
        else:
            # create Count() Structure
            super(ParserElement, self).__init__(initializer=Count())
            self.pattern = hre.group(pattern)  # for every Count() there must be a group
        self._compiled = None
    
    # LOGIC
    # =====
    
    @overrides # TODO does this work - new parameter silent
    def group(self, wrapper=lambda x:x, pseudo=False, liftkeys=False, silent=None):
        # this is inplace:
        super(ParserElement, self).group(wrapper, pseudo=pseudo, liftkeys=liftkeys)
        # normal grouping is done by Structure type,
        # but silent groups are nevertheless needed for correct regex semantics:
        if silent is None:
            pass # keep old self.pattern, this is mainly needed for pseudo groups like created for ResultNames
        elif silent:
            self.pattern = hre.silent_group(self.pattern)
        else:
            self.pattern = hre.group(self.pattern)
        self._compiled = None
        return self
    
    def suppress(self):
        """Suppresses the output of this C{ParserElement}; useful to keep punctuation from
           cluttering up returned output.
           
           change all inner brackets, e.g. (...) or (?P<>...) or (?<>...) to non-capturing (?:...) version
           
           CAUTION: NOT REVERSIBLE!
        """
        self.pattern = hre.begins_not_silently_grouped.sub("(?:", self.pattern)
        self._compiled = None
        self.clear()
        return self
    
    def repeat(self, min=0, max=None):
        # TODO there is something wrong here. After studying the suppress case,
        # TODO it seems as if repeat silent=False is just wrong. There are silent repeats
        # TODO or if there are always unsilent repeats, how to make a suppressed-like repeat?

        # TODO it seems to me that suppressed groups must be labeled to see from above whether a group is suppressed
        # TODO and then take the correct variant (silent=False/True, and Leaf/noLeaf) of repeat

        # TODO or an alternativ thought: maybe make all repeats silent and instead track all real groups
        # TODO through the same map (keys should be managed by references between these groups)
        # TODO in fact only such groups over an repeated element must be Leafed
        """ repeat on arbitrary ParserElement """
        if max is not None and min > max:
            raise RuntimeError("min <= max needed")
        # if there is at most one real group in the pattern,
        # then there is no structure so far at all
        # and thus we do not have to group, but just can repeat
        # (mind by .suppress() there may also be zero real groups, which also don't have to be grouped)
        if len(hre.begins_not_silently_grouped.findall(self.pattern)) <= 1:
            # we still need to group silently so to not break anything
            # (otherwise e.g. UNH...'{1, 99} appears, which instead of repeating the "group", just will repeat the last element)
            self.pattern = hre.ensure_grouping(self.pattern)
        else:
            # the grouping is done by wrapping into a Leaf,
            # so that we can construct a map function which does all restructuring of the regex output
            self.group(
                wrapper = lambda struct: Leaf(self.Repeated(Count(), struct)),
                pseudo = True,
                liftkeys = True,
                silent = False, # this adds a grouping level also in the pattern
            )
        if max is None:
            self.pattern = r"%s{%s,}"   % (self.pattern, min)
        elif min == max:
            self.pattern = r"%s{%s}"    % (self.pattern, min)
        else:
            self.pattern = r"%s{%s,%s}" % (self.pattern, min, max)
        self._compiled = None
    
    @staticmethod
    def _transform_match_gen(match):
        try:
            for i in it.count(1):
                yield ParserElement.MatchedGroup(match.ends(i), match.captures(i))
        except IndexError:
            pass
    
    def _parseString(self, instring):
        """starts matchin at starts of ``instring`` - no search
        
        this is copying everything beforehand"""
        
        if self._compiled is None:
            self._compiled = regex.compile(self.pattern)
        
        m = self._compiled.match(instring)
        if m is None:
            return None
        
        mymatch = list(self._transform_match_gen(m))
        
        Count.reset()
        cp = deepcopy(self)
        cp.map(self._recursive_evalcount)
        cp.map(self._func_parse_leaf(mymatch))
        # getting default structure str, repr interface (also for nested elements):
        # (for speed advantage, this line can be commented
        #  str / repr of ParserElement are adapted to Structure for this reason)
        recursive_structure_delift(cp)
        pr = ParseResult(cp, span=m.span())
        return pr
    
    @staticmethod
    def _recursive_evalcount(leaf):
        """ evaluates all Count instances so that they refer to fixed group """
        # TODO it would be faster, if the value is afterwards directly available
        if isinstance(leaf, ParserElement.Repeated):
            leaf.count.eval()
            leaf.struct.map(ParserElement._recursive_evalcount)
        elif isinstance(leaf, Count):
            leaf.eval()
        return leaf
    
    @staticmethod
    def _func_parse_leaf(match):
        """
        CAUTION: for this map to work correctly,
        every Count instance must be evaluated already recursively!
        
        i.e. first map ParserElement._recursive_evalcount
        """
        
        def recursive_parse(leaf, maxend=None):
            # recursive case:
            if isinstance(leaf, ParserElement.Repeated):
                def gen():
                    for i, end in enumerate(match[leaf.count.value].ends):
                        if maxend is not None and end > maxend:
                            del match[leaf.count.value].ends[:i] #delete everything parsed so far
                            # captures are of no interest at all of these Repeated elements
                            # so no need to delete them
                            break
                        yield deepcopy(leaf.struct).map(partial(recursive_parse, maxend=end))
            
                # returns structure which is labeld pseudo by initial repeat method
                # return reduce(op.add, gen())
                
                # alternatively return simple list, which is flattened out automatically
                # (same effect as pseudo structure, however one could process this repetitions further,
                # e.g. keeping only last repition like it is done in pyparsing for default)
                return list(gen())
            
            # base case:
            elif isinstance(leaf, Count):
                if maxend is None:
                    ret = match[leaf.value].captures[:]
                    del match[leaf.value].captures[:]
                    del match[leaf.value].ends[:]
                else:
                    i = -1
                    for i, end in enumerate(match[leaf.value].ends):
                        if end > maxend:
                            # i is now the final valid index+1
                            break
                    else:
                        # no break, i.e. we currently miss the last one, OR empty loop
                        i += 1 # if nothing was done, i=0 now, giving empty list and no deletes

                    ret = match[leaf.value].captures[:i]
                    # delete everything parsed so far (both captures end ends!):
                    del match[leaf.value].captures[:i]
                    del match[leaf.value].ends[:i]
                return ret
            
        return recursive_parse
    
    def __iadd__(self, other):
        if isinstance(other, basestring):
            other = ParserElement(regex.escape(other))
        Structure.__iadd__(self, other)
        self.pattern += other.pattern
        self._compiled = None
        return self
    
    def __radd__(self, other):
        if isinstance(other, basestring):
            other = ParserElement(regex.escape(other))
        other += self
        return other
        
    def __ior__(self, other):
        if isinstance(other, basestring):
            other = ParserElement(regex.escape(other))
        
        Structure.__iadd__(self, other)
        self.pattern += "|" + other.pattern
        self.group(pseudo = True,
                   liftkeys = True,
                   silent = True)
        return self
    
    def __ror__(self, other):
        if isinstance(other, basestring):
            other = ParserElement(regex.escape(other))
        other |= self
        other.group(pseudo = True,
                    liftkeys = True,
                    silent = True)
        return other
    
    """ # for speed just let it be the default output
    def __str__(self):
        return "(r'%s', %s)" % (self.pattern, Structure.__str__(self))
    
    def __repr__(self):
        return "(r'%s', %s)" % (self.pattern, Structure.__repr__(self))
    """




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
            base += expr
        return base
    except StopIteration: # only one element
        return first


def MatchFirst(iterable):
    """__dict__ of first element will be passed through MatchFirst result """
    try:
        gen = iter(iterable)
        base = next(gen) | next(gen) # once (|) to have a new element
        for expr in gen:
            base |= expr
        return base
    except StopIteration: # only one element
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