#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""AST nodes for promotable expressions."""

from mjast import Statement, Expression
from mjast import (identifier, arguments, keyword, type_identifier)


class PromotableExpression(Statement, Expression):
    def __init__(self, code):
        super().__init__(code)


class MethodCall(PromotableExpression):
    _parts = (("lhs", "method"), ("arguments", ))

    def __init__(self, code):
        self.expression = (
            identifier("method"),
            arguments(),
        )
        super().__init__(code)


class ObjectConstruction(PromotableExpression):
    def __init__(self, code):
        self.expression = (
            keyword("new"),
            type_identifier(),
            arguments(),
        )
        super().__init__(code)
