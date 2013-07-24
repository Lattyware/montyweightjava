#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Components to do core parsing."""

from functools import partial

import mjast
from exceptions import SyntaxException
from tokenizer import Token


def _consume(code, *types, value=None):
    type_description = types[0]
    potential = code.current
    if potential.type not in types:
        raise SyntaxException(Token(type_description, value, None, None, None),
                              potential, potential.source, potential.line,
                              potential.pos)
    elif value is not None and potential.value != value:
        raise SyntaxException(Token(types[0], value, None, None, None),
                              potential, potential.source, potential.line,
                              potential.pos)
    else:
        next(code)
        return potential


def _statement(code, close=True):
    potentials = [
        (((Token.symbol, ";"), ), mjast.NoOp),
        (((Token.keyword, "if"), ), mjast.Conditional),
        (((Token.identifier, None), (Token.assignment_operator, None)),
         mjast.VariableAssignment),
        (((Token.identifier, None), (Token.symbol, ".")), _promoted),
        (((Token.identifier, None), (Token.prepostfix_operator, None)),
         _promoted),
        (((Token.keyword, "return"), ), mjast.Return),
        (((Token.symbol, "{"), ), mjast.Block),
        (((Token.keyword, "new"), ), mjast.ObjectConstruction),
        (((Token.keyword, "while"), ), mjast.WhileLoop),
        (((Token.keyword, "for"), ), mjast.ForLoop),
        (((Token.prepostfix_operator, None), ), mjast.PrefixOperation),
        (((Token.identifier, None), ), mjast.LocalVariableDeclaration),
        ((), _promoted),
    ]
    stmt = _switch(code, "a statement", potentials)
    if close and stmt.must_be_closed:
        _consume(code, Token.symbol, value=";")
    return stmt


def _brackets(code):
    code.rollback_mark()
    try:
        value = mjast.Cast(code)
        code.discard_rollback()
        return value
    except SyntaxException:
        code.rollback()
        value = mjast.OperationGroup(code)
        return value


def _expression(code, limit=False):
    potentials = [
        (((Token.symbol, "("), ), _brackets),
        (((Token.keyword, "new"), ), mjast.ObjectConstruction),
        (((Token.identifier, None), ), mjast.Variable),
        (((Token.string_literal, None), ), mjast.StringLiteral),
        (((Token.number_literal, None), ), mjast.NumberLiteral),
        (((Token.decimal_literal, None), ), mjast.DecimalLiteral),
        (((Token.boolean_literal, None), ), mjast.BooleanLiteral),
        (((Token.null_literal, None), ), mjast.NullLiteral),
        (((Token.prepostfix_operator, None), ), mjast.PrefixOperation),
        (((Token.prefix_operator, None), ), mjast.PrefixOperation),
        (((Token.preinfix_operator, None), ), mjast.PrefixOperation),
    ]
    expr = _switch(code, "an expression", potentials)
    current = code.current
    if current.fits(Token.symbol, "."):
        next(code)
        right = _recursive_expression(code, expr)
        if right:
            return right
    if (current.fits(Token.ternary_operator) or
            current.fits(Token.prepostfix_operator) or
            current.fits(Token.preinfix_operator) or
            current.fits(Token.infix_operator)) and not limit:
        right = _recursive_expression(code, expr)
        if right:
            return right
    return expr


def _promoted(code, unused=None):
    expr = _expression(code, limit=True)
    potentials = [
        (((Token.identifier, None), (Token.symbol, "(")), mjast.MethodCall),
        (((Token.identifier, None), (Token.assignment_operator, None)),
         mjast.FieldAssignment),
        (((Token.prepostfix_operator, None), ), mjast.PostfixOperation),
    ]
    statement = _switch(code, "a method call, postfix operator or"
                              " field assignment", potentials, True)
    if statement:
        statement.lhs = expr
        return statement
    elif isinstance(expr, mjast.Statement):
        return expr
    else:
        raise SyntaxException("a method call, postfix operator or"
                              " field assignment", code.current,
                              code.current.source, code.current.line,
                              code.current.pos)


def _recursive_expression(code, left):
    potentials = [
        (((Token.prepostfix_operator, None), ), mjast.PostfixOperation),
        (((Token.preinfix_operator, None), ), mjast.InfixOperation),
        (((Token.infix_operator, None), ), mjast.InfixOperation),
        (((Token.ternary_operator, "?"), ), mjast.TernaryOperation),
        (((Token.identifier, None), (Token.symbol, "(")), mjast.MethodCall),
        (((Token.identifier, None), (Token.assignment_operator, None)), None),
        (((Token.identifier, None), ), mjast.FieldAccess),
        (((Token.symbol, "("), ), mjast.OperationGroup),
    ]
    expr = _switch(code, "an operation, method call or field access",
                   potentials, True)
    if not expr:
        return left
    expr.lhs = left
    current = code.current
    if current.fits(Token.symbol, "."):
        next(code)
        return _recursive_expression(code, expr)
    if (current.fits(Token.ternary_operator) or
            current.fits(Token.prepostfix_operator) or
            current.fits(Token.preinfix_operator) or
            current.fits(Token.infix_operator)):
        return _recursive_expression(code, expr)
    return expr


def _switch(code, expected, potentials, allow_null=False):
    tokens = list(code._stored)
    for expected_tokens, statement in potentials:
        if all(type_ in {token.type, None} and value in {token.value, None}
               for (type_, value), token in zip(expected_tokens, tokens)):
            if statement:
                return statement(code)
            else:
                break
    if not allow_null:
        token = tokens[0]
        raise SyntaxException(expected, token, token.source, token.line,
                              token.pos)


def _identifier_or_star(code):
    if code.current.fits(Token.infix_operator, "*"):
        return _consume(code, Token.infix_operator, value="*")
    else:
        return _consume(code, Token.identifier)


def parameters(name="parameters"):
    return ListPart(name, mjast.Parameter)


def arguments(name="arguments"):
    return ListPart(name, _expression)


def type_identifier(name="type"):
    return delegate(name, mjast.Type)


def keyword(value=None):
    return Part(Token.keyword, value=value)


def keyword_using_token(name, action, value):
    return UsingPart(name, action, Token.keyword, value)


def generics(name="generics"):
    return ListPart(name, mjast.Type, ((Token.infix_operator, "<"),
                                       (Token.infix_operator, ">")))


def dotted_name(name="dotted_name"):
    return ListPart(name, _identifier_or_star, False, (Token.symbol, "."))


def statements(name="statements"):
    return until(name, symbol("}"), _statement)


def statement(name, close=True):
    return SubNodePart(name, partial(_statement, close=close))


def identifier(name):
    return NamedPart(name, Token.identifier)


def name(value_function=None, *args):
    if value_function:
        return Part(Token.identifier, value_function=value_function, args=args)
    else:
        return Part(Token.identifier)


def operator(*types, value=None):
    if value:
        return Part(*types, value=value)
    else:
        return NamedPart("operator", *types)


def symbol(value=None):
    return Part(Token.symbol, value=value)


def until(name, part, action, peek=False):
    return UntilPart(name, part, action, peek)


def constructors(cls, action):
    return ConstructorPart(cls, action)


def expression(name):
    return SubNodePart(name, _expression)


def delegate(name, to):
    return SubNodePart(name, to)


def literal(name, type_):
    return NamedPart(name, type_)


def exists(name, part):
    return ExistsPart(name, part)


class If:
    def __init__(self, condition):
        self.condition = condition


class Else:
    pass


class EndIf:
    pass


class Part:
    many = False

    def __init__(self, *types, value=None, value_function=None, args=()):
        self.types = types
        self._value = value
        self.value_function = value_function
        self.args = args

    @property
    def value(self):
        if self.value_function is not None:
            return self.value_function(*self.args)
        else:
            return self._value

    def parse(self, code):
        value = _consume(code, *self.types, value=self.value)
        return value, value

    def __add__(self, other):
        return ParseExpression([self, other])

    def __repr__(self):
        return "Part({}, value={}, value_function={})".format(
            ", ".join(self.types), self.value, self.value_function)


class NamedPart(Part):
    many = False

    def __init__(self, name, *types):
        self.name = name
        self.types = types

    def parse(self, code):
        value = _consume(code, *self.types)
        return value, value

    def __repr__(self):
        return "NamedPart({!r}, {})".format(self.name, ", ".join(self.types))


class UsingPart(Part):
    many = False

    def __init__(self, name, action, *types, value=None):
        self.name = name
        self.types = types
        self.action = action
        self.value_function = None
        self._value = value

    def parse(self, code):
        value = self.action(using=_consume(code, *self.types, value=self.value))
        return value, value

    def __repr__(self):
        return "UsingPart({!r}, {}, {}, value={})".format(
            self.name, self.action, ", ".join(self.types), self.value)


class ExistsPart(NamedPart):
    many = False

    def __init__(self, name, part):
        self.name = name
        self.part = part

    def parse(self, code):
        try:
            value = self.part.parse(code)
        except SyntaxException:
            return False, None
        return True, value

    def __repr__(self):
        return "ExistsPart({!r}, {!r})".format(self.name, self.part)


class SubNodePart(Part):
    many = False

    def __init__(self, name, action):
        self.name = name
        self.action = action

    def parse(self, code):
        part = self.action(code)
        return part, part

    def __repr__(self):
        return "SubNodePart({!r}, {})".format(self.name, self.action)


class UntilPart(NamedPart):
    many = True

    def __init__(self, name, part, action, peek):
        self.name = name
        self.part = part
        self.action = action
        self.peek = 1 if peek else 0

    def parse(self, code):
        results = []
        while not (code.stored(self.peek).type in self.part.types and
                   (self.part.value is not None and
                    code.stored(self.peek).value == self.part.value)):
            results.append(self.action(code))
        return results, results[-1] if results else None

    def __repr__(self):
        return "UntilPart({!r}, {}, {})".format(self.name, self.part,
                                                self.action)


class ConstructorPart(NamedPart):
    many = True

    def __init__(self, cls, action):
        self.name = "constructors"
        self.cls = cls
        self.action = action

    def parse(self, code):
        results = []
        while (code.current.fits(Token.identifier, self.cls.name.value) and
               code.peek.fits(Token.symbol, "(")):
            results.append(self.action(code))
        return results, results[-1] if results else None

    def __repr__(self):
        return "UntilPart({!r}, {}, {})".format(self.name, self.part,
                                                self.action)


class ListPart(NamedPart):
    many = True

    def __init__(self, name, action, delimiters=((Token.symbol, "("),
                                                 (Token.symbol, ")")),
                 separator=(Token.symbol, ",")):
        self.name = name
        self.action = action
        self.delimiters = delimiters
        self.separator = separator

    def parse(self, code):
        if self.delimiters:
            _consume(code, self.delimiters[0][0], value=self.delimiters[0][1])
        items = []
        first = True
        condition = (self._condition_on_delimiters
                     if self.delimiters else self._condition_no_delimiters)
        while condition(code.current, first):
            if first:
                first = False
            else:
                _consume(code, self.separator[0], value=self.separator[1])
            items.append(self.action(code))
        last = items[-1] if items else None
        if self.delimiters:
            last = _consume(code, self.delimiters[1][0], value=self.delimiters[1][1])
        return items, last

    def _condition_on_delimiters(self, current, first):
        return not current.fits(self.delimiters[1][0],
                                value=self.delimiters[1][1])

    def _condition_no_delimiters(self, current, first):
        return current.fits(self.separator[0], value=self.separator[1]) or first

    def __repr__(self):
        return "ListPart({!r}, {})".format(self.name, self.action)


class ParseExpression:
    def __init__(self, components):
        self.components = components

    def __add__(self, other):
        return ParseExpression(self.components + other.components)

    def parse(self, parent):
        last = None
        if_ = None
        for part in self.components:
            if isinstance(part, If):
                if_ = part.condition(parent)
            elif isinstance(part, Else):
                if_ = not if_
            elif isinstance(part, EndIf):
                if_ = None
            elif if_ is None or if_:
                value, temp = part.parse(parent.code)
                if temp:
                    last = temp
                if hasattr(part, "name"):
                    setattr(parent, part.name, value)
        return last
