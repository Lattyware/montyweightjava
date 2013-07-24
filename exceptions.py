#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Exceptions."""

from abc import ABCMeta, abstractmethod

import tokenizer


_vowels = set("AEIOUaeiou")


def a_or_an(follows):
    return "a" if follows[0] not in _vowels else "an"


def construct_code_error(short_description, source, line, pos, description):
    print("{} error in \"{}\" on line {} at position {}:".format(
        short_description, source, line, pos))
    spaces = (pos - 1) * " "
    indent = "\t"
    with open(source) as source:
        for line_no, text in enumerate(source, 1):
            if line_no == line:
                print(indent + text.replace("\t", " ").rstrip())
                print(indent + spaces + "^")
    print(indent + spaces + description)


class ParsingException(Exception, metaclass=ABCMeta):
    """A base class for exceptions that occur during parsing."""
    def __init__(self):
        self._type = "An"
        self.line = 0
        self.pos = 0
        self.source = None

    def print_error(self):
        construct_code_error(self._type, self.source, self.line, self.pos,
                             str(self))

    @abstractmethod
    def __str__(self):
        pass


class UnexpectedEOFException(ParsingException):
    _type = "Unexpected end of file"

    def __init__(self, expecting=None, source=None, line=None, pos=None):
        if line is None != pos is None:
            raise ValueError("If line is given, pos must be, and visa-versa.")
        self.line = line
        self.pos = pos
        self.source = source
        if isinstance(expecting, tokenizer.Token):
            self.expecting = "{} ({} {})" if expecting.value else "{1} {2}"
            self.expecting = self.expecting.format(repr(expecting.value),
                                                   a_or_an(expecting.type),
                                                   expecting.type)
        else:
            self.expecting = expecting

    def print_error(self):
        if self.line is None and self.pos is None:
            print("Unexpected end of file in \"{}\" before tokenizer "
                  "initialised.".format(self.source))
            if self.expecting:
                print("Expecting {}.".format(self.expecting))
        else:
            super().print_error()

    def __str__(self):
        if self.expecting:
            return "Unexpected EOF, expecting {}.".format(self.expecting)
        else:
            return "Unexpected EOF."


class SyntaxException(ParsingException):
    """An exception for where the code doesn't make sense syntactically."""
    _type = "Syntax"

    def __init__(self, expecting, got, source, line, pos):
        if isinstance(expecting, tokenizer.Token):
            self.expecting = "{} ({} {})" if expecting.value else "{1} {2}"
            self.expecting = self.expecting.format(repr(expecting.value),
                                                   a_or_an(expecting.type),
                                                   expecting.type)
        else:
            self.expecting = expecting
        if isinstance(got, tokenizer.Token):
            self.got = "{} ({} {})" if got.value else "{1} {2}"
            self.got = self.got.format(repr(got.value), a_or_an(got.type),
                                       got.type)
        else:
            self.got = got
        self.source = source
        self.line = line
        self.pos = pos

    def __str__(self):
        return "Expecting {}, got {}.".format(
            self.expecting, self.got)


class InvalidLiteralException(SyntaxException):
    """An exception for where there is an invalid literal value in the code."""
    _type = "Invalid literal"

    def __str__(self):
        return "Invalid {} literal, {}.".format(
            self.expecting, self.got)


class AnalyserException(Exception, metaclass=ABCMeta):
    """A base class for all exceptions during interpretation."""
    def __init__(self, source, line, pos):
        self._type = "An"
        self.line = line
        self.pos = pos
        self.source = source

    def print_error(self):
        construct_code_error(self._type, self.source, self.line, self.pos,
                             str(self))

    @abstractmethod
    def __str__(self):
        pass


class TypeException(AnalyserException):
    """A base class for all exceptions during interpretation."""
    _type = "Type"

    def __init__(self, type, source, line, pos):
        self.type = type
        self.line = line
        self.pos = pos
        self.source = source

    def __str__(self):
        return "The type '{}' does not exist.".format(self.type)


class SanityException(AnalyserException):
    """A base class for all exceptions during interpretation."""
    _type = "Sanity"

    def __init__(self, description, source, line, pos):
        self.description = description
        self.line = line
        self.pos = pos
        self.source = source

    def __str__(self):
        return self.description


class InterpreterException(Exception, metaclass=ABCMeta):
    """A base class for all exceptions during interpretation."""
    def __init__(self, description, stack, source, line, pos):
        self.description = description
        self.stack = stack
        self.line = line
        self.pos = pos
        self.source = source

    def __str__(self):
        return self.description

    def print_traceback(self):
        print("Traceback (most recent call last):".format(
              self.source, self.line, self.pos))
        print(self.stack)
        indent = "    "
        with open(self.source) as source:
            for line_no, text in enumerate(source, 1):
                if line_no == self.line:
                    print(indent + text.strip())
        print(self.description)


class ExecutionException(InterpreterException):
    _type = "Execution"
