#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""The interpreter."""

import sys

from parser import parse_handling_errors
import mjast as nodes
import sematics
from tokenizer import Token
from exceptions import (ExecutionException,
                        InterpreterException, TypeException)
import library
import classes


class Variable:
    """A variable during execution."""

    def __init__(self, type_, value=None, scope=None):
        if type_ is None:
            assert(value is None)
            self.type = classes.Object(scope)
            self.value = None
            return
        if isinstance(type_, classes.Class):
            self.type = type_
        else:
            if scope is None:
                raise ValueError("If type_ is not a class, scope must be "
                                 "given.")
            self.type = scope.type(type_)
        self.value = value

    def __iter__(self):
        yield self.type
        yield self.value

    def __getitem__(self, item):
        if item == 0:
            return self.type
        elif item == 1:
            return self.value
        else:
            raise KeyError("Index out of range.")

    def __repr__(self):
        return "({}){!r}".format(str(self.type), str(self.value))


class CacheNode:
    def __init__(self, value=None):
        self.value = value
        self.children = {}

    def get(self, rest, generics, static=False):
        try:
            item = next(rest)
            return self.children[item].get(rest, generics, static)
        except StopIteration:
            if static:
                return self.value
            try:
                return self.children[generics].value
            except KeyError:
                return self.value

    def create(self, rest, generics, static):
        new = CacheNode()
        try:
            item = next(rest)
            self.children[item] = new
            return new.create(rest, generics, static)
        except StopIteration:
            if static:
                return self
            else:
                self.children[generics] = new
                return new

    def __repr__(self):
        return "CacheNode({}, {})".format(str(self.value), str(self.children))


class CacheTree:
    def __init__(self):
        self.children = {}

    def get(self, first, rest, generics, static=False):
        try:
            if static:
                return self.children[first].value
            return self.children[first].get(iter(rest), tuple(generics), static)
        except KeyError:
            return None

    def set(self, first, rest, generics, value):
        if generics is None:
            static = True
        else:
            static = False
            generics = tuple(generics)
        node = CacheNode()
        bottom = node.create(iter(rest), generics, static)
        bottom.value = value
        self.children[first] = node


class Frame:
    def __init__(self, description, call):
        self.description = description
        self.call = call

    def __repr__(self):
        target = self.call.token.line
        file = self.call.token.source
        line, no = None, 0
        if target:
            with open(file) as source:
                for no, line in enumerate(source, 1):
                    if no == target:
                        break
        if line and no:
            return "    {}\n  File {!r}, line {}, in {}:".format(
                line.strip(), file, no, self.description)
        else:
            return "  File {}, in {}.".format(file, self.description)


class Stack:
    def __init__(self):
        self.stack = []

    def enter(self, frame):
        self.stack.append(frame)

    def exit(self):
        return self.stack.pop()

    @property
    def current(self):
        return self.stack[-1]

    @property
    def parent(self):
        return self.stack[-2]

    def __iter__(self):
        yield from self.stack

    def __repr__(self):
        return "\n".join(repr(frame) for frame in self.stack[1:])


class Scope:
    def __init__(self, description, outer, types=None, variables=None,
                 *, stack=None):
        self.description = description
        self.outer = outer
        self.stack = stack if stack is not None else outer.stack
        self.types = types if types is not None else {}
        self.top = self.outer.top if self.outer else self
        self.variables = variables if variables is not None else {}
        self.cache = CacheTree()

    def generic(self, generic):
        return self.types[generic]

    def type(self, target, generics=(), top_level=None, static=False,
             resolve_generics=False):
        if target is None or isinstance(target, classes.Class):
            return target
        if isinstance(target, classes.Generic):
            return self.generic(target) if resolve_generics else target

        if isinstance(target, tuple):
            target, generics = target
        if isinstance(target, nodes.Type):
            generics = target.generics
            target = target.type.value

        if top_level is None:
            top_level = self

        generics = [top_level.type(generic) for generic in generics]

        if isinstance(target, classes.Generic):
            first, rest = target, ()
        else:
            first, *rest = target.split(".")

        ret = self.cache.get(first, rest, generics, static)
        if ret is not None:
            return ret

        if first in self.types:
            current = self.types[first]
        elif not self.outer:
            raise KeyError("No such class {!r}.".format(target))
        else:
            current = self.outer.type(first, generics, top_level, True)

        for part in rest:
            current = current.children[part]
        if isinstance(current, classes.Generic):
            self.cache.set(first, rest, None, ret)
            return current
        if static or isinstance(current, classes.Class):
            self.cache.set(first, rest, None, ret)
            return current
        ret = current(top_level, generics=generics)
        self.cache.set(first, rest, generics, ret)
        return ret

    def value(self, target):
        if target in self.variables:
            return self.variables[target]
        else:
            try:
                return self.type(target, static=True)(self, static=True)
            except KeyError:
                if not self.outer:
                    raise KeyError("No such variable {!r}.".format(target))
                else:
                    return self.outer.value(target)

    def __repr__(self):
        return "[Scope: {}]".format(self.description)


def string_literal(expression, scope):
    return Variable(scope.type("java.lang.String"),
                    bytes(expression.value.value, "utf-8").decode(
                        "unicode_escape"))


def number_literal(expression, scope):
    return Variable(classes.primitive_types["int"](scope),
                    int(expression.value.value))


def decimal_literal(expression, scope):
    return Variable(classes.primitive_types["float"](scope),
                    float(expression.value.value))


def boolean_literal(expression, scope):
    return Variable(classes.primitive_types["boolean"](scope),
                    expression.value.value == "true")


def null_literal(expression, scope):
    return Variable(classes.Object, None)


def variable(expression, scope):
    try:
        return scope.value(expression.name.value)
    except KeyError:
        token = expression.token
        raise ExecutionException("Variable {!r} does not exist in this "
                                 "scope!".format(expression.name.value),
                                 scope.stack, token.source, token.line,
                                 token.pos)


def instance_of(expression, scope):
    lhs = evaluate(expression.lhs, scope)
    rhs = evaluate(expression.rhs, scope)
    return Variable("boolean", lhs.type.check(rhs))


def ternary_expression(expression, scope):
    if evaluate(expression.lhs, scope).value:
        return evaluate(expression.true_case, scope)
    else:
        return evaluate(expression.false_case, scope)


def plus(lhs, rhs=None):
    if rhs is None:
        value = lhs.value
    else:
        value = lhs.value + rhs.value
    return type(lhs.type), value


def minus(lhs, rhs=None):
    if rhs is None:
        value = -lhs.value
    else:
        value = lhs.value - rhs.value
    return type(lhs.type), value


_operations = {
    ">": lambda lhs, rhs: (classes.primitive_types["boolean"],
                           lhs.value > rhs.value),
    "<": lambda lhs, rhs: (classes.primitive_types["boolean"],
                           lhs.value < rhs.value),
    "+": plus,
    "-": minus,
    "instanceof": lambda lhs, rhs: (classes.primitive_types["boolean"],
                                    lhs.value.cls == rhs),
    "*": lambda lhs, rhs: (lhs.type, lhs.value * rhs.value),
    "/": lambda lhs, rhs: (classes.primitive_types["int"],
                           lhs.value // rhs.value),
    "%": lambda lhs, rhs: (classes.primitive_types["int"],
                           lhs.value % rhs.value),
    "==": lambda lhs, rhs: (classes.primitive_types["boolean"],
                            lhs.value == rhs.value),
    "!=": lambda lhs, rhs: (classes.primitive_types["boolean"],
                            lhs.value != rhs.value),
    ">=": lambda lhs, rhs: (classes.primitive_types["boolean"],
                            lhs.value >= rhs.value),
    "<=": lambda lhs, rhs: (classes.primitive_types["boolean"],
                            lhs.value <= rhs.value),
    "&&": lambda lhs, rhs: (classes.primitive_types["boolean"],
                           lhs.value and rhs.value),
    "&": lambda lhs, rhs: (lhs.type, lhs.value & rhs.value),
    "||": lambda lhs, rhs: (classes.primitive_types["boolean"],
                           lhs.value or rhs.value),
    "|": lambda lhs, rhs: (lhs.type, lhs.value | rhs.value),
    "^": lambda lhs, rhs: (lhs.type, lhs.value ^ rhs.value),
    "<<": lambda lhs, rhs: (lhs.type, lhs.value << rhs.value),
    ">>": lambda lhs, rhs: (lhs.type, lhs.value >> rhs.value),
    ">>>": lambda lhs, rhs: (lhs.type, lhs.value >> rhs.value),
    "!": lambda rhs: (classes.primitive_types["boolean"], not rhs.value),
    "~": lambda rhs: (rhs.type, ~rhs.value),
}


def operation(expression, scope):
    args = [evaluate(getattr(expression, part), scope)
            for part in ("lhs", "rhs") if hasattr(expression, part)]
    type_, value = _operations[expression.operator.value](*args)
    if isinstance(type_, type):
        type_ = type_(scope)
    return Variable(type_, value)


def object_construction(expression, scope):
    cls = scope.type(expression.type)
    args = [evaluate(arg, scope) for arg in expression.arguments]
    return Variable(cls, cls.instance(args, scope, call=expression))


def field_access(expression, scope):
    item = evaluate(expression.lhs, scope)
    name = expression.field.value
    if isinstance(item, library.LibClass):
        return getattr(item, name)
    else:
        return item.value.scope.value(name)


def method_call(statement, scope):
    item = evaluate(statement.lhs, scope)
    arguments = [evaluate(argument, scope)
                 for argument in statement.arguments]
    if isinstance(item, Variable):
        item = item.value
    if item is None:
        token = statement.lhs.token
        raise ExecutionException("Null Pointer Exception", scope.stack,
                                 token.source, token.line, token.pos)
    return item.run_method(statement.method.value, arguments, scope,
                           call=statement)


def cast(expression, scope):
    type_ = scope.type(expression.type)
    target = evaluate(expression.target, scope)
    return Variable(type_, target.value)


def operation_group(expression, scope):
    return evaluate(expression.operation, scope)


_evaluate = {
    nodes.StringLiteral: string_literal,
    nodes.NumberLiteral: number_literal,
    nodes.DecimalLiteral: decimal_literal,
    nodes.BooleanLiteral: boolean_literal,
    nodes.NullLiteral: null_literal,
    nodes.Variable: variable,
    nodes.TernaryOperation: ternary_expression,
    nodes.InfixOperation: operation,
    nodes.PrefixOperation: operation,
    nodes.PostfixOperation: operation,
    nodes.ObjectConstruction: object_construction,
    nodes.FieldAccess: field_access,
    nodes.MethodCall: method_call,
    nodes.Cast: cast,
    nodes.OperationGroup: operation_group,
}


def evaluate(expression, scope):
    value = _evaluate[type(expression)](expression, scope)
    value.token = expression.token
    return value


def local_variable(statement, scope):
    required_type = scope.type(statement.type)
    if statement.value:
        type_, value = evaluate(statement.value, scope)
    else:
        type_, value = required_type, required_type.default_value
    if not type_.is_subclass_of(required_type):
        raise ExecutionException("Type mismatch!", statement.token.source,
                                 statement.token.line, statement.token.pos)
    else:
        scope.variables[statement.name.value] = Variable(required_type,
                                                         value, scope)


def while_loop(statement, scope):
    scope = Scope("While Loop (Line {})".format(statement.token.line),
                  scope)
    while evaluate(statement.check, scope).value:
        execute(statement.statements, scope)


def for_loop(statement, scope):
    scope = Scope("For Loop (Line {})".format(statement.token.line),
                  scope)
    execute([statement.setup], scope)
    statements = statement.statements + [statement.iteration]
    while evaluate(statement.check, scope).value:
        execute(statements, scope)


def conditional(statement, scope):
    scope = Scope("Conditional (Line {})".format(statement.token.line),
                  scope)
    check = evaluate(statement.check, scope).value
    if check:
        execute(statement.true_case, scope)
    elif statement.elseif:
        execute([statement.elseif], scope)
    elif statement.false_case:
        execute(statement.false_case, scope)


def variable_assignment(statement, scope):
    name = statement.name.value
    try:
        target = scope.value(name)
    except KeyError as e:
        raise ExecutionException(
            "Variable {!r} does not exist!".format(name),
            statement.token.source, statement.line, statement.pos) from e
    actual_type, rhs = evaluate(statement.value, scope)
    if target.type != actual_type:
        raise ExecutionException("Type mismatch!", statement.token.source,
                                 statement.line, statement.pos)
    o = statement.operator.value
    try:
        target.value = assignment_operator(o, target.value, rhs)
    except KeyError as e:
        raise ExecutionException("Unknown operator {}!".format(o),
                                 statement.token.source, statement.line,
                                 statement.pos) from e


_assignment_operators = {
    "=": lambda old, rhs: rhs,
    "+=": lambda old, rhs: old + rhs,
    "-=": lambda old, rhs: old - rhs,
    "*=": lambda old, rhs: old * rhs,
    "/=": lambda old, rhs: old / rhs,
    "|=": lambda old, rhs: old | rhs,
    "&=": lambda old, rhs: old & rhs,
    "%=": lambda old, rhs: old % rhs,
    "^=": lambda old, rhs: old ^ rhs,
    "<<=": lambda old, rhs: old << rhs,
    ">>=": lambda old, rhs: old >> rhs,
    ">>>=": lambda old, rhs: old >> rhs
}


def assignment_operator(operator, old_value, rhs):
    return _assignment_operators[operator](old_value, rhs)


def prefix_operation(statement, scope):
    target = evaluate(statement.rhs, scope)
    o = statement.operator.value
    if o == "++":
        target.value += 1
    elif o == "--":
        target.value -= 1
    return target


def postfix_operation(statement, scope):
    target = evaluate(statement.lhs, scope)
    old_value = Variable(*target)
    o = statement.operator.value
    if o == "++":
        target.value += 1
    elif o == "--":
        target.value -= 1
    return old_value


def field_assignment(statement, scope):
    instance = evaluate(statement.lhs, scope).value
    rhs = evaluate(statement.rhs, scope)
    name = statement.field.value
    value = instance.scope.value(name)
    o = statement.operator.value
    try:
        value.value = assignment_operator(o, value.value, rhs.value)
    except KeyError as e:
        raise ExecutionException("Unknown operator {}!".format(o),
                                 statement.token.source, statement.token.line,
                                 statement.token.pos) from e


def ret(statement, scope):
    if statement.value:
        raise classes.Return(evaluate(statement.value, scope))
    else:
        raise classes.Return()


def no_op(statement, scope):
    #pass
    raise Exception  # NoOps disabled to ensure they don't mask errors.


def type_check(name, arguments, parameters, scope, token):
    if len(arguments) != len(parameters):
        raise TypeException("{} takes {} arguments. {} "
                            "given.".format(name, len(parameters),
                                            len(arguments)), token.source,
                            token.line, token.pos)
    for num, (argument, parameter) in enumerate(zip(arguments, parameters), 1):
        a, p = argument.type, parameter.type
        if not isinstance(a, classes.Class):
            a = scope.type(a)
        if not isinstance(p, classes.Class):
            p = scope.type(p)
        if not a.check(p):
            raise TypeException("{!r} parameter {!r} ({}) takes "
                                "type {}, but {} was "
                                "given.".format(name, parameter.name,
                                                num, p, a),
                                argument.token.source, argument.token.line,
                                argument.token.pos)


def block(statement, scope):
    scope = Scope("Anonymous Block (Line {})".format(statement.token.line),
                  scope)
    execute(statement.statements, scope)


_execute = {
    nodes.LocalVariableDeclaration: local_variable,
    nodes.WhileLoop: while_loop,
    nodes.MethodCall: method_call,
    nodes.VariableAssignment: variable_assignment,
    nodes.Conditional: conditional,
    nodes.PostfixOperation: postfix_operation,
    nodes.PrefixOperation: prefix_operation,
    nodes.ForLoop: for_loop,
    nodes.FieldAssignment: field_assignment,
    nodes.Return: ret,
    nodes.NoOp: no_op,
    nodes.Block: block,
}


def execute(statements, scope):
    for statement in statements:
        _execute[type(statement)](statement, scope)


def interpret(program_node, name):
    stack = Stack()
    stack.enter(Frame("Global", program_node))
    global_scope = Scope("Global", None, types=classes.primitive_types,
                         stack=stack)
    stdlib = library.load_standard_library()
    java = stdlib["java"]
    global_scope.types["java"] = java
    global_scope.types.update(java.children["lang"].children)
    for imp in program_node.imports:
        imp_name = imp.name
        star = False
        if imp_name[-1].fits(Token.symbol, "*"):
            star = True
            imp_name.pop()
        names = iter(imp_name[:-1])
        last = imp_name[-1]
        current = stdlib[next(names).value]
        for cls_name in names:
            current = current.children[cls_name.value]
            if not current.static:
                raise KeyError("Not static.")
        current = current.children[last.value]
        if star:
            global_scope.types.update(current.children)
        else:
            global_scope.types[current.name] = current
    mains = []
    for class_node in program_node.classes:
        cls = classes.Class.native_class(class_node)
        global_scope.types[cls.name] = cls
        if any(method.name.value == "main" and method.static
               for method in cls.methods):
            mains.append(cls)
    assert(len(mains) == 1)  # Semantic analyser should catch this.
    program_node.token = Token(0, 0, name, None, None)
    mains[0](global_scope, static=True).run_method("main", (), global_scope,
                                                   call=program_node)

if __name__ == "__main__":
    import argparse

    args = argparse.ArgumentParser(
        description='Interpret Middleweight Java Code.')
    args.add_argument('file', metavar='FILE', type=argparse.FileType('r'),
                      default=sys.stdin, help='The source code to interpret.')

    args = args.parse_args()

    program = parse_handling_errors(args.file)
    sematics.analyse_handling_errors(program)
    if program:
        try:
            interpret(program, args.file.name)
        except InterpreterException as e:
            e.print_traceback()
    else:
        sys.exit(1)
