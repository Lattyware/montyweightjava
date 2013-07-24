#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Tokenizer to take characters and produce tokens, ready to be parsed."""

import string
import functools
import collections
import exceptions
import itertools


class Token(object):
    whitespace = "whitespace"
    symbol = "symbol"
    string_literal = "string"
    number_literal = "number"
    decimal_literal = "decimal"
    boolean_literal = "boolean"
    null_literal = "null"
    identifier = "identifier"
    keyword = "keyword"

    assignment_operator = "assignment operator"
    prepostfix_operator = "prefix/postfix operator"
    preinfix_operator = "prefix/infix operator"
    prefix_operator = "prefix operator"
    infix_operator = "infix operator"
    ternary_operator = "ternary operator"

    def __init__(self, type_, value, source, line, pos):
        self.type = type_
        self.value = value
        self.source = source
        if self.value:
            self.length = len(self.value)
        if type_ == Token.string_literal:
            self.value = value[1:-1]
        self.line = line
        self.pos = pos

    def tree(self):
        return [self.value]

    def fits(self, type_, value=None):
        if self.type == type_:
            return value is None or value == self.value
        return False

    def __str__(self):
        return repr(self.value)

    def __repr__(self):
        return "Token({}, {})".format(repr(self.type), repr(self.value))


class StoredPeekIterator(object):
    def __init__(self, iterator, store=2):
        self.finished = False
        self.iterator = iterator
        self._backtracks = []
        self._stored = collections.deque(maxlen=store)
        for _ in range(store):
            self._stored.append(next(self.iterator))

    def __iter__(self):
        return self

    def rollback_mark(self):
        self._backtracks.append((list(self._stored), []))

    def rollback(self):
        stored, backtrack = self._backtracks.pop()
        self._stored.extend(stored)
        self.iterator = itertools.chain(backtrack, self.iterator)

    def discard_rollback(self):
        del self._backtracks[-1]

    def __next__(self):
        if not len(self._stored):
            raise StopIteration
        try:
            new = next(self.iterator)
            self._stored.append(new)
            for _, backtrack in self._backtracks:
                backtrack.append(new)
        except StopIteration:
            return self._stored.popleft()
        return self._stored[0]

    def stored(self, item):
        try:
            return self._stored[item]
        except IndexError as e:
            raise StopIteration from e

    @property
    def current(self):
        return self._stored[0]

    @property
    def peek(self):
        try:
            return self._stored[1]
        except IndexError:
            return None


class Tokenizer(object):
    whitespace = set(string.whitespace)
    string_delimiters = set("'\"")
    decimal_point = {"."}
    digits = set(string.digits)
    booleans = {"true", "false"}
    null = "null"
    keywords = {"if", "else", "return", "super", "class", "extends",
                "void", "new", "while", "for", "import", "static"}

    operator_types = {
        Token.assignment_operator: {"=", "/=", "*=", "+=", "-=", "|=", "&=",
                                    "%=", "^=", "<<=", ">>=", ">>>="},
        Token.prefix_operator: {"!", "~"},
        Token.prepostfix_operator: {"++", "--"},
        Token.preinfix_operator: {"+", "-"},
        Token.infix_operator: {"*", "/", "%", "==", "!=", ">", ">=",
                               "<", "<=", "instanceof", "&&", "||",
                               "<<", ">>", ">>>", "&", "^", "|"},
        Token.ternary_operator: {"?", ":"},
    }

    operator_to_type = {value: type_ for type_, values in operator_types.items()
                        for value in values}

    operators = set().union(*operator_types.values())
    symbols = set(";{}().,<>") | set("".join(operators - {"instanceof"}))

    def __init__(self, source):
        self.source = source.name
        self.code = source
        self.look_ahead = 1

    def _identify(self, character, line_no, pos):
        if character in Tokenizer.symbols:
            return Token.symbol, self._symbol
        elif character in Tokenizer.digits:
            return Token.number_literal, self._number
        elif character in Tokenizer.whitespace:
            return Token.whitespace, self._whitespace
        elif character in Tokenizer.string_delimiters:
            return self._string(character, line_no, pos)
        else:
            return Token.identifier, self._identifier

    def _symbol(self, character, line_no, pos):
        if character in Tokenizer.symbols:
            return False, self._symbol
        else:
            return self._identify(character, line_no, pos)

    def _string(self, character, line_no, pos, delimiter=None):
        if delimiter:
            if character == delimiter:
                return False, self._identify
            else:
                if character == "\n":
                    raise exceptions.InvalidLiteralException("string",
                                                             "no end "
                                                             "delimiter "
                                                             "before EOL ("
                                                             "expecting {})"
                                                             .format(
                                                                 delimiter
                                                             ), self.source,
                                                             line_no, pos)
                return False, functools.partial(self._string,
                                                delimiter=delimiter)
        if character in Tokenizer.string_delimiters:
            return Token.string_literal, functools.partial(self._string,
                                                           delimiter=character)
        else:
            return self._identify(character, line_no, pos)

    def _identifier(self, character, line_no, pos):
        if character not in Tokenizer.whitespace | Tokenizer.symbols \
                | Tokenizer.string_delimiters:
            return False, self._identifier
        else:
            return self._identify(character, line_no, pos)

    def _number(self, character, line_no, pos):
        if character in self.digits | self.decimal_point:
            return False, self._number
        else:
            return self._identify(character, line_no, pos)

    def _whitespace(self, character, line_no, pos):
        if character in Tokenizer.whitespace:
            return False, self._whitespace
        else:
            return self._identify(character, line_no, pos)

    def __call__(self):
        return StoredPeekIterator(self._tokenize(), self.look_ahead + 1)

    def _post_process(self, token, token_type, line_no, start):
        if token_type == Token.identifier:
            if token in Tokenizer.keywords:
                token_type = Token.keyword
            elif token in Tokenizer.booleans:
                token_type = Token.boolean_literal
            elif token == Tokenizer.null:
                token_type = Token.null_literal
            elif token == "instanceof":
                token_type = Token.infix_operator
        if token_type == Token.number_literal and "." in token:
            token_type = Token.decimal_literal
        if token_type == Token.symbol:
            while token:
                for l in range(3, 0, -1):
                    current, other = token[:l], token[l:]
                    if current in Tokenizer.operators:
                        yield Token(Tokenizer.operator_to_type[current],
                                    current, self.source, line_no, start)
                        start += l
                        token = other
                        break
                else:
                    l = 1
                    current, other = token[:l], token[l:]
                    yield Token(token_type, current, self.source, line_no,
                                start)
                    start += l
                    token = other
            return
        yield Token(token_type, token, self.source, line_no, start)

    def _tokenize(self):
        token_type = None
        token = ""
        state = self._identify
        start = 1
        line_no = 0
        for line_no, line in enumerate(self.code, 1):
            for pos, character in enumerate(line, 1):
                new_token, state = state(character, line_no, pos)
                if new_token:
                    if token and token_type != Token.whitespace:
                        yield from self._post_process(token, token_type,
                                                      line_no, start)
                    token_type = new_token
                    token = character
                    start = pos
                else:
                    token += character
        if token and token_type != Token.whitespace:
            yield from self._post_process(token, token_type, line_no, start)
