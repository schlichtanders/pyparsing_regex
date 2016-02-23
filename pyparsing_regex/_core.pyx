#!/usr/bin/python
# -*- coding: utf-8 -*-

import pyximport; pyximport.install()
import regex
import sys
import abc
from functools import partial

from schlichtanders.myobjects_cython import Count, Structure
import pyparsing_regex._helpers_regex as hre
from pprint import pformat

import cPickle
import ujson

serializer = ujson

def deepcopy(o):
    """fast deepcopy alternative"""
    return cPickle.loads(cPickle.dumps(o, -1))

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
    def __init__(self, count, structure):
        self.count = count
        self.structure = structure

    def __str__(self):
        return "Repeated{count: %s, structure: %s}" % (str(self.count), str(self.structure))


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
            self.structure = Structure()
            self.pattern = pattern
            self.name = self.pattern
        else:
            # create Count() Structure
            self.structure = Structure(Count())
            self.pattern = hre.group(pattern)  # for every Count() there must be a group
            self.name = self.pattern
        self._compiled = None

    # LOGIC
    # =====

    def group(self, wrapper=None, pseudo=False, liftkeys=False, silent=None):
        # this is inplace:
        self.structure.group(wrapper, pseudo=pseudo, liftkeys=liftkeys)
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
        self.structure.set_name(name)
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
        self.structure.clear()
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
        struct_iter = iter(self.structure)
        firstelem = next(struct_iter)
        try:
            next(struct_iter)
            struct_len_1 = False
        except StopIteration:
            struct_len_1 = True

        if struct_len_1 and isinstance(firstelem, Repeated):
            # prevent nested repeatings Repeat(Repeat)
            self.pattern = hre.ensure_grouping(self.pattern)

        else:
            # the grouping is done by wrapping into a Leaf,
            # so that we can construct a map function which does all restructuring of the regex output
            self.group(
                wrapper = lambda structure: Repeated(Count(), structure), # creates a complete Structure element
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
        struct = deepcopy(self.structure)

        mymatch, substructs, preprocess_func = self._parse_preprocess(match)
        struct.map(preprocess_func)
        struct.map(self._func_parse_leaf(mymatch, substructs))
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
        substructs = {} #{Count: substruct}
        def preprocess_func(leaf):
            """ evaluates all Count instances so that they refer to fixed group """
            if isinstance(leaf, Repeated):
                new_leaf = leaf.count.value # evaluates and stores value directly # TODO this is already somewhat in structure... we could ask for the idx, which would be the same, wouldn't it?
                # CAUTION: +1 as we now start counting at 0
                match_transformed.append(match.ends(new_leaf + 1))
                # recursive call
                leaf.structure.map(preprocess_func)
                # from here on everything is executed depth first (by recursion)
                # substructs_dumped[new_leaf] = serializer.dumps(leaf.structure)
                substructs[new_leaf] = leaf.structure

            # elif isinstance(leaf, Count):
            else: #there should be no other case
                new_leaf = leaf.value # evaluates and stores value directly
                # CAUTION: +1 as we now start counting at 0
                match_transformed.append(match.captures(new_leaf + 1))

            return new_leaf # new_leaf is int

        return match_transformed, substructs, preprocess_func


    @staticmethod
    def _func_parse_leaf(mymatch, substructs):
        """
        CAUTION: for this map to work correctly,
        every Count instance must be evaluated and directly available (recursively!)
        i.e. first map ParserElement._recursive_evalcount
        """
        def recursive_parse(leaf, maxend=None):
            try: # Repeated structure
                substruct = substructs[leaf]
                # """
                def gen():
                    if maxend is None:
                        for end in mymatch[leaf]: # repeated elements have ends while leafs have captures
                            yield substruct.map(partial(recursive_parse, maxend=end), inplace=False)
                    else:
                        for i, end in enumerate(mymatch[leaf]):
                            if end > maxend:
                                del mymatch[leaf][:i] #delete everything parsed so far
                                # captures are of no interest at all of these Repeated elements
                                break
                            yield substruct.map(partial(recursive_parse, maxend=end), inplace=False)

                # returns structure which is labeld pseudo by initial repeat method
                # return reduce(op.add, gen())

                # alternatively return simple list, which is flattened out automatically
                # (same effect as pseudo structure, however one could process this repetitions further,
                # e.g. keeping only last repition like it is done in pyparsing for default)
                return list(gen())

            except KeyError: # base case:
                # this is always a single entry
                return mymatch[leaf].pop(0)
        return recursive_parse

    def __iadd__(self, other):
        if isinstance(other, basestring):
            other = ParserElement(regex.escape(other))
        self.structure += other.structure
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

        self.structure += other.structure
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
        return "['%s', %s]" % (self.name, str(self.structure))

    def __repr__(self):
        # [] are for pprint, () would make more sense
        return "['%s', %s, r'%s']" % (self.name, repr(self.structure), self.pattern)




# copy for non-cyclic imports:
class StringEnd(ParserElement):
    def __init__(self):
        """matches the end of the text"""
        super(StringEnd, self).__init__(r"$")
