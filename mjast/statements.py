#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""AST nodes for statements."""

from tokenizer import Token

from mjast import Node
from mjast import (identifier, keyword, symbol, expression, statements,
                   statement, operator, If, EndIf, delegate, type_identifier)


class Statement(Node):
    must_be_closed = True

    def __init__(self, code):
        super().__init__(code)


class NoOp(Statement):
    _parts = ((), ())

    def __init__(self, code):
        super().__init__(code)

    def _parse(self):
        pass


class WhileLoop(Statement):
    must_be_closed = False

    def __init__(self, code):
        self.expression = (
            keyword("while"),
            symbol("("),
            expression("check"),
            symbol(")"),
            symbol("{"),
            statements(),
            symbol("}"),
        )
        super().__init__(code)


class ForLoop(Statement):
    must_be_closed = False

    def __init__(self, code):
        self.expression = (
            keyword("for"),
            symbol("("),
            statement("setup", False),
            symbol(";"),
            expression("check"),
            symbol(";"),
            statement("iteration", False),
            symbol(")"),
            symbol("{"),
            statements(),
            symbol("}"),
        )
        super().__init__(code)


class Conditional(Statement):
    must_be_closed = False

    def __init__(self, code):
        self.false_case = []
        self.expression = (
            keyword("if"),
            symbol("("),
            expression("check"),
            symbol(")"),
            symbol("{"),
            statements("true_case"),
            symbol("}"),
            If(lambda self: self.code.current.fits(Token.keyword, "else") and
               self.code.peek.fits(Token.keyword, "if")),
            keyword("else"),
            delegate("elseif", Conditional),
            EndIf(),
            If(lambda self: self.code.current.fits(Token.keyword, "else") and
               not self.code.peek.fits(Token.keyword, "if")),
            keyword("else"),
            symbol("{"),
            statements("false_case"),
            symbol("}"),
            EndIf(),
        )
        super().__init__(code)


class FieldAssignment(Statement):
    _parts = (("lhs", "field", "operator", "rhs"), ())

    def __init__(self, code):
        self.expression = (
            identifier("field"),
            operator(Token.assignment_operator),
            expression("rhs")
        )
        super().__init__(code)


class LocalVariableDeclaration(Statement):
    def __init__(self, code):
        self.expression = (
            type_identifier(),
            identifier("name"),
            If(LocalVariableDeclaration._assignment),
            operator(Token.assignment_operator),
            expression("value"),
            EndIf(),
        )
        super().__init__(code)

    @staticmethod
    def _assignment(inst):
        return inst.code.current.fits(Token.assignment_operator, value="=")


class VariableAssignment(Statement):
    def __init__(self, code):
        self.expression = (
            identifier("name"),
            operator(Token.assignment_operator),
            expression("value"),
        )
        super().__init__(code)


class Return(Statement):
    def __init__(self, code):
        self.expression = (
            keyword("return"),
            If(lambda self: not self.code.current.fits(Token.symbol, ";")),
            expression("value"),
            EndIf(),
        )
        super().__init__(code)


class Block(Statement):
    must_be_closed = False

    def __init__(self, code):
        self.expression = (
            symbol("{"),
            statements(),
            symbol("}"),
        )
        super().__init__(code)
