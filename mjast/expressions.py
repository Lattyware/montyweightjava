#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""AST nodes for expressions."""

from mjast import Node, Statement
from mjast import (identifier, symbol, expression, operator, literal,
                   type_identifier)
import mjast

from tokenizer import Token


class Expression(Node):
    def __init__(self, code):
        super().__init__(code)


class OperationGroup(Expression):
    operation = None

    def __init__(self, code):
        self.expression = (
            symbol("("),
            expression("operation"),
            symbol(")"),
        )
        super().__init__(code)


class Operation(Expression):
    pass


class PrefixOperation(Operation, Statement):
    def __init__(self, code):
        self.expression = (
            operator(Token.prefix_operator, Token.prepostfix_operator,
                     Token.preinfix_operator),
            expression("rhs"),
        )
        super().__init__(code)


class PostfixOperation(Operation, Statement):
    def __init__(self, code):
        self.expression = (
            operator(Token.prepostfix_operator),
        )
        super().__init__(code)


class InfixOperation(Operation):
    _parts = (("lhs", "operator", "rhs"), ())

    def __init__(self, code=None):
        if not code:
            self.lhs = None
            self.operator = None
            self.rhs = None
        else:
            self.expression = (
                operator(Token.infix_operator, Token.preinfix_operator),
                expression("rhs"),
            )
            super().__init__(code)


class TernaryOperation(Operation):
    _parts = (("lhs", "true_case", "false_case"), ())

    def __init__(self, code):
        self.expression = (
            operator(Token.ternary_operator, value="?"),
            expression("true_case"),
            operator(Token.ternary_operator, value=":"),
            expression("false_case"),
        )
        super().__init__(code)


class Literal(Expression):
    type_ = None

    def __init__(self, code):
        self.expression = (
            literal("value", self.type_),
        )
        super().__init__(code)


class StringLiteral(Literal):
    type_ = Token.string_literal


class NumberLiteral(Literal):
    type_ = Token.number_literal


class DecimalLiteral(Literal):
    type_ = Token.decimal_literal


class BooleanLiteral(Literal):
    type_ = Token.boolean_literal


class NullLiteral(Literal):
    _parts = ((), ())
    type_ = Token.null_literal


class Variable(Expression):
    def __init__(self, code):
        self.expression = (
            identifier("name"),
        )
        super().__init__(code)


class FieldAccess(Expression):
    _parts = (("lhs", "field"), ())

    def __init__(self, code):
        self.expression = (
            identifier("field"),
        )
        super().__init__(code)


class Cast(Expression):
    _parts = (("type", "target"), ())

    def __init__(self, code, target=None, hack=False):
        if hack:
            self.type = mjast.Type(using=hack)
            self.type.type = code
            self.target = target
            self.token = hack
        else:
            self.expression = (
                symbol("("),
                type_identifier(),
                symbol(")"),
                expression("target"),
            )
            super().__init__(code)
