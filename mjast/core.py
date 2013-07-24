#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Core AST nodes."""

from tokenizer import Token

from mjast import Node
from mjast import (identifier, keyword, symbol, until, parameters,
                   keyword_using_token, arguments, statements, delegate,
                   constructors, If, EndIf, dotted_name, generics,
                   type_identifier, exists, Else)


class Program(Node):
    _parts = ((), ("classes", ))

    def __init__(self, code):
        self.imports = []
        self.classes = []
        super().__init__(code)

    def _parse(self):
        while True:
            current = self.code.current
            if current.type != Token.keyword or current.value != "import":
                break
            else:
                self.imports.append(Import(self.code))
        while self.code.peek is not None:
            self.classes.append(Class(self.code))


class Class(Node):
    def __init__(self, code):
        self.base = None
        self.expression = (
            exists("static", keyword("static")),
            keyword("class"),
            identifier("name"),
            If(lambda self: self.code.current.fits(Token.infix_operator,
                                                   value="<")),
            generics(),
            EndIf(),
            If(lambda self: self.code.current.fits(Token.keyword, "extends")),
            keyword("extends"),
            delegate("base", Type),
            EndIf(),
            symbol("{"),
            until("fields", symbol("("), Field, True),
            constructors(self, Constructor),
            until("methods", symbol("}"), Method),
            symbol("}")
        )
        super().__init__(code)


class Field(Node):
    def __init__(self, code):
        self.expression = (
            type_identifier(),
            identifier("name"),
            symbol(";")
        )
        super().__init__(code)


class Parameter(Node):
    def __init__(self, code):
        self.expression = (
            type_identifier(),
            identifier("name")
        )
        super().__init__(code)


class Constructor(Node):
    def __init__(self, code):
        self.super_arguments = []
        self.expression = (
            identifier("name"),
            parameters(),
            symbol("{"),
            If(lambda self: self.code.current.fits(Token.keyword, "super")),
            keyword("super"),
            arguments("super_arguments"),
            symbol(";"),
            EndIf(),
            statements(),
            symbol("}")
        )
        super().__init__(code)


class Method(Node):
    def __init__(self, code):
        self.expression = (
            exists("static", keyword("static")),
            If(lambda self: self.code.current.fits(Token.infix_operator,
                                                   value="<")),
            generics(),
            EndIf(),
            If(lambda self: self.code.current.fits(Token.keyword,
                                                   value="void")),
            keyword_using_token("type", Type, "void"),
            Else(),
            delegate("type", Type),
            EndIf(),
            identifier("name"),
            parameters(),
            symbol("{"),
            statements(),
            symbol("}")
        )
        super().__init__(code)


class Type(Node):
    _parts = ("type", ), ("generics", )

    def __init__(self, code=None, using=None):
        self.type = None
        self.generics = []
        if code:
            self.expression = (
                identifier("type"),
                If(lambda self: self.code.current.fits(Token.infix_operator,
                                                       value="<")),
                generics(),
                EndIf(),
            )
            super().__init__(code)
        elif using:
            self.token = using
        else:
            raise ValueError("using must be supplied if code is not.")


class Import(Node):
    _parts = ("name", ), ()

    def __init__(self, code=None):
        self.name = None
        if code:
            self.expression = (
                keyword("import"),
                dotted_name("name"),
                symbol(";"),
            )
            super().__init__(code)
