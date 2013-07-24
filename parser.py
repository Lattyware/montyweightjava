#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""A parser for MWJ, producing an abstract syntax tree from a text file
containing suitable code."""

import sys

import mjast
import exceptions
from tokenizer import Tokenizer

mjast.node.DEBUG = False


def parse(source):
    tokenizer = Tokenizer(source)
    tokens = None
    try:
        tokens = tokenizer()
        return mjast.Program(tokens)
    except StopIteration as e:
        expecting = e.args[0] if e.args else None
        if tokens:
            current = tokens.current
            raise exceptions.UnexpectedEOFException(expecting, source.name,
                                                    current.line,
                                                    current.pos) from e
        else:
            raise exceptions.UnexpectedEOFException(expecting,
                                                    source.name) from e


def parse_handling_errors(source):
    try:
        return parse(source)
    except exceptions.ParsingException as e:
        e.print_error()
        sys.exit(1)


if __name__ == "__main__":
    target = sys.argv[1]
    with open(target) as source:
        program = parse_handling_errors(source)
        print('Successfully parsed "{}":'.format(target))
        print("\n".join(program.tree()))
        sys.exit(0)
