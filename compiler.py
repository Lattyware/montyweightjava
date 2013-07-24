#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Compile MWJ Code to Python Bytecode."""

from ast import *
import os
import time
import py_compile
import marshal
import sys
import mjast

import parser
import sematics


def program(node, statement):
    for cls in node.classes:
        if any(m.name.value == "main" for m in cls.methods):
            main_class = cls.name.value
    return Module(
        body=[mjast_to_pyast(cls, True) for cls in node.classes] +
             [If(test=Compare(left=Name(id="__name__", ctx=Load()), ops=[Eq()],
                              comparators=[Str("__main__")]),
                 body=[Expr(Call(func=Attribute(value=Name(id=main_class,
                                                           ctx=Load()),
                                                attr="main", ctx=Load()),
                                 args=[], keywords=[], starargs=None,
                                 kwargs=None))], orelse=[])]
    )


def parameter(node, statement):
    return arg(arg=node.name, annoation=None)


def field(node, statement):
    return Assign(
        targets=[Attribute(value=Name(id="self", ctx=Load()),
                           attr=node.name.value,
                           ctx=Store())],
        value=Name(id="None", ctx=Load()),
    )


def string_literal(node, statement):
    return Str(node.value.value)


def field_assignment(node, statement):
    return Assign(
        targets=[Attribute(value=mjast_to_pyast(node.lhs),
                           attr=node.field.value,
                           ctx=Store())],
        value=mjast_to_pyast(node.rhs),
    )


def field_access(node, statement):
    r = Attribute(
        value=mjast_to_pyast(node.lhs),
        attr=node.field.value,
        ctx=Load(),
    )
    if statement:
        r = Expr(r)
    return r


def local_variable_declaration(node, statement):
    if node.value:
        if not node.operator.value == "=":
            raise ValueError("Can't handle other than '='.")
        value = mjast_to_pyast(node.value)
    else:
        value = Name(id="None", ctx=Load())
    return Assign(
        targets=[node.name.value],
        value=value,
    )


def object_construction(node, statement):
    r = Call(
        func=Name(
            id=node.type.type.value,
            ctx=Load(),
        ),
        args=[mjast_to_pyast(arg) for arg in node.arguments],
        keywords=[],
        starargs=None,
        kwargs=None,
    )
    if statement:
        r = Expr(r)
    return r


def method_call(node, statement):
    r = Call(
        func=Attribute(
            value=mjast_to_pyast(node.lhs),
            attr=node.method.value,
            ctx=Load(),
        ),
        args=[mjast_to_pyast(arg) for arg in node.arguments],
        keywords=[],
        starargs=None,
        kwargs=None,
    )
    if node.method.value == "println":
        if (isinstance(node.lhs, mjast.FieldAccess) and
                node.lhs.field.value == "out" and
                isinstance(node.lhs.lhs, mjast.Variable) and
                node.lhs.lhs.name.value == "System"):
            r = Call(
                func=Name(id="print", ctx=Load()),
                args=[mjast_to_pyast(arg) for arg in node.arguments],
                keywords=[],
                starargs=None,
                kwargs=None,
            )
    if statement:
        r = Expr(r)
    return r


def variable(node, statement):
    if node.name.value == "this":
        return Name(id="self", ctx=Load())
    return Name(id=node.name.value, ctx=Load())


def cls(node, statement):
    if not statement:
        raise ValueError("Can't be an expression!")

    if node.base:
        bases = [Name(id=node.base.value, ctx=Load())]
    else:
        bases = []

    constructor = None
    if len(node.constructors) > 1:
        raise ValueError("Can't handle multiple constructors!")
    elif node.constructors:
        constructor, = node.constructors
        constructor_args = [mjast_to_pyast(p) for p in constructor.parameters]

    if node.generics:
        raise ValueError("Can't handle generics!")

    return ClassDef(
        name=node.name.value,
        bases=bases,
        keywords=[],
        starargs=None,
        kwargs=None,
        body=[FunctionDef(
            name="__init__",
            args=arguments(
                args=[arg(arg="self", annotation=None)]+constructor_args,
                vararg=None, varargannotation=None, kwonlyargs=[],
                kwarg=None, kwargannotation=None,
                defaults=[], kw_defaults=[]
            ),
            body=[mjast_to_pyast(field) for field in node.fields] +
            ([mjast_to_pyast(s, True) for s in constructor.statements]
             if constructor and constructor.statements else [Pass()]),
            decorator_list=[],
            returns=None,
        )]+[FunctionDef(
            name=m.name.value,
            args=arguments(
                args=[] if m.static else [arg(arg="self", annotation=None)] +
                     [mjast_to_pyast(p) for p in m.parameters],
                vararg=None, varargannotation=None, kwonlyargs=[],
                kwarg=None, kwargannotation=None,
                defaults=[], kw_defaults=[]
            ),
            body=[mjast_to_pyast(s, True) for s in m.statements]
            if m.statements else [Pass()],
            decorator_list=[Name(id='staticmethod', ctx=Load())]
            if m.static else [],
            returns=None,
            ) for m in node.methods],
        decorator_list=[],
    )


_mjast_to_pyast = {
    mjast.Program: program,
    mjast.Class: cls,
    mjast.LocalVariableDeclaration: local_variable_declaration,
    mjast.Field: field,
    mjast.FieldAssignment: field_assignment,
    mjast.StringLiteral: string_literal,
    mjast.MethodCall: method_call,
    mjast.FieldAccess: field_access,
    mjast.ObjectConstruction: object_construction,
    mjast.Variable: variable,
}


def mjast_to_pyast(node, statement=False):
    return _mjast_to_pyast[type(node)](node, statement)


def compile_to_pyc(program, filename):
    module = mjast_to_pyast(program)
    fix_missing_locations(module)
    #print(dump(module))
    return compile(module, filename, "exec")


if __name__ == "__main__":
    import argparse

    args = argparse.ArgumentParser(
        description='Compile Middleweight Java Code.')
    args.add_argument('file', metavar='FILE', type=argparse.FileType('r'),
                      default=sys.stdin, help='The source code to compile.')

    args = args.parse_args()

    program = parser.parse_handling_errors(args.file)
    sematics.analyse_handling_errors(program)
    name, _ = os.path.splitext(os.path.split(args.file.name)[1])
    if program:
        codeobject = compile_to_pyc(program, args.file.name)
        with open(name.lower() + ".pyc", 'wb') as fc:
            fc.write(py_compile.MAGIC)
            fc.write(b'\0\0\0\0')
            py_compile.wr_long(fc, int(time.time()))
            marshal.dump(codeobject, fc)
    else:
        sys.exit(1)
