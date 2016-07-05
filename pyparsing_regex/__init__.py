""" pyparsing_regex is a reimplementation of the pyparsing interface, building upon regular expressions.

It is intended to be a replacement for pyparsing where no recursion is needed, in order to speed up parsing
significantly (factor 100). The outputs are roughly similar


The index-interface of the parse result is analog to the of pyparsing, i.e. with string-keys "example-key" you can access
all entries where ``setResultName("example-key")`` was called.
Alternatively you can access elements with integer-key, in a list like way.
Important to know, the ``Group`` class creates a nesting within this listing interface.

In addition to pyparsing, pyparsing_regex has a ``GroupLiftKeys`` class which works like ``Group``, only that all keys
are also available at the upper level (encompassing everything which belongs to that key further down). In a normal
``Group``, the nested keys would be hided from the upper layer, which might not be what is wanted.

The returned object is a ``schlichtanders.myobjects.Structure`` which is a general powerful datastructure immitating
pyparsings ParseResult in a general way.
"""
from ._interface import *
__all__ = [
    'deepcopy',
    'Literal', 'Regex', 'Word', 'CharsNotIn', 'SkipTo', 'FollowedBy',
    'Combine', 'Suppress', 'StringStart', 'StringEnd', 'LineStart', 'LineEnd',
    'And', 'MatchFirst', 'Optional', 'Group', 'GroupLiftKeys', 'OneOrMore', 'ZeroOrMore',
    'Repeat', 'setResultsNameInPlace',
    'ParserElement'
]