#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Semantic analysis module - takes an abstract syntax tree and ensures that it
makes sense semantically."""

import sys
import exceptions
import library
import mjast
import classes

from parser import parse_handling_errors


def extract_type(type_):
    if type_.type:
        return (type_.type.value, tuple(extract_type(generic)
                                        for generic in type_.generics))
    else:
        return None, ()


def analyse_handling_errors(program):
    try:
        return analyse(program)
    except exceptions.AnalyserException as e:
        e.print_error()
        sys.exit(1)


def analyse(program, main=True):
    stdlib = library.load_standard_library()

    # Expand all type names to fully qualified ones.
    types = resolve_types(program, stdlib)
    for cls in program.classes:
        class_generics = {generic.type.value for generic in cls.generics}
        if cls.base:
            expand_name(cls.base, types, class_generics)
        for field in cls.fields:
            expand_name(field.type, types, class_generics)
        for const in cls.constructors:
            expand_all_names(const, types, class_generics)
        for method in cls.methods:
            function_generics = {generic.type.value
                                 for generic in method.generics}
            if method.static:
                expand_all_names(method, types, function_generics)
            else:
                expand_all_names(method, types,
                                 class_generics | function_generics)

    if main:
        # Check there is one (and only one) main method.
        found_main = False
        for cls in program.classes:
            for method in cls.methods:
                if (method.name.value == "main" and method.static
                        and not method.parameters and not method.type.type):
                    if found_main:
                        token = method.token
                        raise exceptions.SanityException(
                            "Multiple main() methods defined.", token.source,
                            token.line, token.pos)
                    else:
                        found_main = True
        if not found_main:
            raise exceptions.SanityException(
                "No `static void main()` method found.", program.token.source,
                0, 0)

    shunting_yard(program)

    consistency_check(program, types, stdlib)


operator_precedence = {
    "*": 7,
    "/": 7,
    "%": 7,
    "+": 6,
    "-": 6,
    "<": 5,
    ">": 5,
    "<=": 5,
    ">=": 5,
    "instanceof": 5,
    "==": 4,
    "!=": 4,
    "&": 3,
    "|": 2,
    "&&": 1,
    "||": 0,
}


def shunting_yard(program):
    for node in program:
        if isinstance(node, mjast.InfixOperation):
            output = []
            stack = []
            for type_, part in operation_iterator(node):
                if type_ == "op":
                    if stack and (operator_precedence[part.value] <=
                                  operator_precedence[stack[-1].value]):
                        output.append(stack.pop())
                    stack.append(part)
                else:
                    output.append(part)
            output = list(reversed(output + list(reversed(stack))))
            stack = []
            while output:
                next_ = output.pop()
                if not isinstance(next_, mjast.Node):
                    current = mjast.InfixOperation()
                    current.operator = next_
                    current.rhs = stack.pop()
                    current.lhs = stack.pop()
                    current.token = next_
                    stack.append(current)
                else:
                    stack.append(next_)
            new_node, = stack
            node.operator = new_node.operator
            node.lhs = new_node.lhs
            node.rhs = new_node.rhs


def operation_iterator(node):
    if isinstance(node, mjast.InfixOperation):
        yield from operation_iterator(node.lhs)
        yield "op", node.operator
        yield from operation_iterator(node.rhs)
    else:
        yield "node", node


def consistency_check(program, global_types, stdlib):
    class_info = {cls.name.value: {
        "fields": {field.name.value: type_from_node(field.type)
                   for field in cls.fields},
        "constructors": {tuple(type_from_node(p.type)
                               for p in constructor.parameters)
                         for constructor in cls.constructors},
        "methods": {(tuple(type_from_node(g) for g in method.generics),
                     method.name.value,
                     tuple(type_from_node(p.type) for p in method.parameters)):
                    type_from_node(method.type)
                    for method in cls.methods if not method.static},
        "static_methods": {(tuple(type_from_node(g) for g in method.generics),
                            method.name.value,
                            tuple(type_from_node(p.type)
                           for p in method.parameters)):
                           type_from_node(method.type)
                           for method in cls.methods if method.static},
        "generics": [type_from_node(g) for g in cls.generics],
        "base": type_from_node(cls.base) if cls.base else ("java.lang.Object",
                                                           ())
    } for cls in program.classes}
    for cls in program.classes:
        generics = [generic.type.value for generic in cls.generics]
        cls_type = cls.name.value, tuple((generic, ())
                                         for generic in generics)
        if cls.base:
            type_from_node(cls.base, class_info, stdlib, generics)
        for constructor in cls.constructors:
            locals_ = dict((p.name.value, type_from_node(p.type, class_info,
                                                         stdlib, generics))
                           for p in constructor.parameters)
            locals_.update({"this": cls_type})
            expected_return = None
            check_statements(constructor.statements, locals_, expected_return,
                             generics, class_info, stdlib, global_types)
        for method in cls.methods:
            method_generics = [generic.type.value
                               for generic in method.generics]
            locals_ = {}
            if not method.static:
                all_generics = generics + method_generics
                locals_.update({"this": cls_type})
            else:
                all_generics = method_generics
            locals_.update(dict((p.name.value, type_from_node(
                p.type, class_info, stdlib, all_generics))
                for p in method.parameters))
            expected_return = type_from_node(method.type, class_info, stdlib,
                                             all_generics)
            check_statements(method.statements, locals_, expected_return,
                             all_generics, class_info, stdlib, global_types)
            if not any(isinstance(s, mjast.Return) for s in method.statements):
                if expected_return != (None, ()):
                    token = method.type.token
                    raise exceptions.SanityException(
                        "Method has no return statement and non-void return "
                        "type '{}'.".format(type_str(expected_return)),
                        token.source, token.line, token.pos)


def local_variable_declaration(statement, token, locals_, generics, class_info,
                               stdlib, global_types, expected_return=None):
    name = statement.name.value
    if name in locals_:
        raise exceptions.SanityException(
            "Local variable '{}' already declared.".format(name),
            token.source, token.line, token.pos)
    else:
        locals_[name] = type_from_node(statement.type, class_info, stdlib,
                                      generics)
        if statement.value:
            check_expression(locals_, generics, class_info,
                             stdlib, global_types, statement.value,
                             locals_[name])


def variable_assignment(statement, token, locals_, generics, class_info, stdlib,
                        global_types, expected_return=None):
    name = statement.name.value
    if name == "this":
        raise exceptions.SanityException(
            "Can't assign to 'this'.".format(name),
            token.source, token.line, token.pos)
    elif name not in locals_:
        raise exceptions.SanityException(
            "Local variable '{}' not declared.".format(name),
            token.source, token.line, token.pos)
    else:
        check_expression(locals_, generics, class_info,
                         stdlib, global_types, statement.value, locals_[name])


def generic_name(type_):
    return (type_.name, ()) if isinstance(type_, classes.Generic) else type_


def method_call(statement, token, locals_, generics, class_info, stdlib,
                global_types, expected_return=None):
    actual = check_expression(locals_, generics, class_info, stdlib,
                              global_types, statement.lhs)
    static = False
    if not isinstance(actual, tuple):
        actual = actual, ()
        static = True
    name = statement.method.value
    arguments = [check_expression(locals_, generics, class_info, stdlib,
                                  global_types, a)
                 for a in statement.arguments]
    _, cls_generics = actual
    for cls_name, _ in resolve_mro(actual, generics, class_info, stdlib, token):
        if cls_name in class_info:
            info = class_info[cls_name]
            call_generics = info["generics"]
            if static:
                methods = info["static_methods"]
            else:
                methods = info["methods"]
        else:
            cls = get_stdlib_class(cls_name, stdlib, token)
            call_generics = [(g, ()) for g in cls.generics]
            tmp = ((m, getattr(cls, m)) for m in cls.methods)
            methods = {((), m, tuple(map(generic_name, f.types))):
                       generic_name(f.return_type)
                       for m, f in tmp if f.static == static}
        generics_replacement = dict(zip(call_generics, cls_generics))
        methods = {(mg, tuple(replace_generics(generics_replacement, p)
                              for p in m)):
                   return_type for (mg, n, m), return_type in methods.items()
                   if n == name}
        for (method_generics, parameters), return_type in methods.items():
            if len(parameters) == len(arguments):
                matched_mg = dict(generics_replacement)
                for p, a in zip(parameters, arguments):
                    fill_generics(matched_mg, method_generics, p, a)
                parameters = [replace_generics(matched_mg, p)
                              for p in parameters]
                if check_arguments(parameters, arguments, generics, class_info,
                                   stdlib):
                    return replace_generics(matched_mg, return_type)
    raise exceptions.SanityException(
        "No method '{}.{}({})'.".format(
            type_str(actual), name, ", ".join(type_str(a)
                                              for a in arguments)),
        token.source, token.line, token.pos)


def fill_generics(matched_mg, method_generics, p, a):
    p_name, p_generics = p
    a_name, a_generics = a
    if p_name == a_name:
        if len(p_generics) == len(a_generics):
            for subp, suba in zip(p_generics, a_generics):
                fill_generics(matched_mg, method_generics, subp, suba)
    elif p in method_generics:
        matched_mg[p] = a


def replace_generics(replacements, type_):
    if type_:
        name, generics = type_
        if type_ in replacements:
            return replacements[type_]
        else:
            return name, tuple(replace_generics(replacements, g)
                               for g in generics)


def object_construction(expression, token, locals_, generics, class_info,
                        stdlib, global_types, expected_return=None):
    actual = type_from_node(expression.type, class_info, stdlib, generics)
    a_name, a_generics = actual
    arguments = [check_expression(locals_, generics, class_info, stdlib,
                                  global_types, a)
                 for a in expression.arguments]
    if a_name in class_info:
        info = class_info[a_name]
        generics = info["generics"]
        constructors = info["constructors"]
    else:
        cls = get_stdlib_class(a_name, stdlib, token)
        generics = [(g, ()) for g in cls.generics]
        constructors = [getattr(cls, c).types for c in cls.constructors]
    generics = dict(zip(generics, a_generics))
    constructors = [tuple(replace_generics(generics, p) for p in c)
                    for c in constructors]
    if not any(check_arguments(constructor, arguments,
                               generics, class_info, stdlib)
               for constructor in constructors):
        raise exceptions.SanityException(
            "No constructor '{}({})'.".format(type_str(actual), ", ".join(
                type_str(a) for a in arguments)),
            token.source, token.line, token.pos)
    return actual


def for_loop(statement, token, locals_, generics, class_info, stdlib,
             global_types, expected_return):
    loop_scope = dict(locals_)
    check_statements([statement.setup], loop_scope,
                     expected_return, generics, class_info, stdlib,
                     global_types)
    check_expression(loop_scope, generics, class_info, stdlib, global_types,
                     statement.check, ("boolean", ()))
    check_statements([statement.iteration] + statement.statements,
                     loop_scope, expected_return, generics, class_info, stdlib,
                     global_types)


def while_loop(statement, token, locals_, generics, class_info, stdlib,
             global_types, expected_return):
    loop_scope = dict(locals_)
    check_expression(loop_scope, generics, class_info, stdlib, global_types,
                     statement.check, ("boolean", ()))
    check_statements(statement.statements,
                     loop_scope, expected_return, generics, class_info, stdlib,
                     global_types)


def conditional(statement, token, locals_, generics, class_info, stdlib,
             global_types, expected_return):
    conditional_scope = dict(locals_)
    check_expression(conditional_scope, generics, class_info, stdlib,
                     global_types, statement.check, ("boolean", ()))
    statements = list(statement.true_case)
    if statement.elseif:
        statements.append(statement.elseif)
    if statement.false_case:
        statements.extend(statement.false_case)
    check_statements(statements, conditional_scope, expected_return,
                     generics, class_info, stdlib, global_types)


def prefix_operation(expression, token, locals_, generics, class_info, stdlib,
                     global_types, expected_return=None):
    actual = check_expression(locals_, generics, class_info, stdlib,
                              global_types, expression.rhs)
    allowable = {
        "++": ("int", "float"),
        "+": ("int", "float"),
        "-": ("int", "float"),
        "--": ("int", "float"),
        "!": ("boolean", ),
        "~": ("boolean", "int", "float"),
    }
    operation = expression.operator.value
    valid = False
    for type_ in allowable[operation]:
        if type_check(actual, (type_, ()), generics, class_info, stdlib):
            valid = True
    if not valid:
        raise exceptions.SanityException(
            "'{}' is only valid on {}.".format(
                operation, ", ".join(allowable[operation])),
            token.source, token.line, token.pos)
    return actual


def postfix_operation(expression, token, locals_, generics, class_info, stdlib,
                     global_types, expected_return=None):
    actual = check_expression(locals_, generics, class_info, stdlib,
                              global_types, expression.lhs)
    allowable = {
        "++": ("int", "float"),
        "--": ("int", "float"),
    }
    operation = expression.operator.value
    valid = False
    for type_ in allowable[operation]:
        if type_check(actual, (type_, ()), generics, class_info, stdlib):
            valid = True
    if not valid:
        raise exceptions.SanityException(
            "'{}' is only valid on {}.".format(
                operation, ", ".join(allowable[operation])),
            token.source, token.line, token.pos)
    return actual


def infix_operation(expression, token, locals_, generics, class_info, stdlib,
                     global_types, expected_return=None):
    lhs = check_expression(locals_, generics, class_info, stdlib,
                           global_types, expression.lhs)
    rhs = check_expression(locals_, generics, class_info, stdlib,
                           global_types, expression.rhs)
    allowable = {
        "+": (("int", "float", "java.lang.String"), None),
        "-": (("int", "float"), None),
        "*": (("int", "float"), None),
        "/": (("int", "float"), None),
        "%": (("int", "float"), None),
        "==": (("java.lang.Object", ), ("boolean", ())),
        "instanceof": (("java.lang.Object", ), ("boolean", ())),
        "!=": (("java.lang.Object", ), ("boolean", ())),
        ">": (("java.lang.Object", ), ("boolean", ())),
        "<": (("java.lang.Object", ), ("boolean", ())),
        ">=": (("java.lang.Object", ), ("boolean", ())),
        "<=": (("java.lang.Object", ), ("boolean", ())),
        "&": (("int", ), None),
        "|": (("int", ), None),
        "^": (("int", ), None),
        ">>": (("int", ), None),
        ">>>": (("int", ), None),
        "<<": (("int", ), None),
        "&&": (("boolean", ), None),
        "||": (("boolean", ), None),
    }
    operation = expression.operator.value
    valid = False
    types, return_type = allowable[operation]
    for type_ in types:
        if (type_check(lhs, (type_, ()), generics, class_info, stdlib) and
                type_check(rhs, (type_, ()), generics, class_info, stdlib)):
            valid = True
            break
    if not valid:
        raise exceptions.SanityException(
            "'{}' is only valid on {} (both operands must be the same), "
            "not {} and {}.".format(
                operation, ", ".join(allowable[operation][0]), type_str(lhs),
                type_str(rhs)),
            token.source, token.line, token.pos)
    else:
        if not return_type:
            return_type = type_, ()
    return return_type


def return_(statement, token, locals_, generics, class_info, stdlib,
            global_types, expected_return):
    if statement.value:
        value = check_expression(locals_, generics, class_info, stdlib,
                                 global_types, statement.value)
    else:
        value = None, ()
    type_check(value, expected_return, generics, class_info, stdlib, token)


def field_assignment(statement, token, locals_, generics, class_info, stdlib,
                     global_types, expected_return):
    lhs = check_expression(locals_, generics, class_info, stdlib,
                           global_types, statement.lhs)
    actual = check_expression(locals_, generics, class_info, stdlib,
                              global_types, statement.rhs)
    cls_name, cls_generics = lhs
    name = statement.field.value
    if cls_name in class_info:
        info = class_info[cls_name]
        try:
            expected = info["fields"][name]
        except KeyError:
            raise exceptions.SanityException(
                "No field '{}' on '{}'.".format(
                    name, type_str(actual)),
                token.source, token.line, token.pos)
    else:
        get_stdlib_class(cls_name, stdlib, token)
        raise exceptions.SanityException(
            "Can't assign to standard library fields.".format(
                name, type_str(actual)),
            token.source, token.line, token.pos)
    type_check(actual, expected, generics, class_info, stdlib, token)


def block(statement, token, locals_, generics, class_info, stdlib,
          global_types, expected_return):
    block_scope = dict(locals_)
    check_statements(statement.statements, block_scope,
                     expected_return, generics, class_info, stdlib,
                     global_types)


statement_handlers = {
    mjast.ObjectConstruction: object_construction,
    mjast.LocalVariableDeclaration: local_variable_declaration,
    mjast.VariableAssignment: variable_assignment,
    mjast.MethodCall: method_call,
    mjast.ForLoop: for_loop,
    mjast.PrefixOperation: prefix_operation,
    mjast.PostfixOperation: postfix_operation,
    mjast.Conditional: conditional,
    mjast.Return: return_,
    mjast.WhileLoop: while_loop,
    mjast.FieldAssignment: field_assignment,
    mjast.NoOp: lambda *args: None,
    mjast.Block: block,
}


def check_statements(statements, locals_, expected_return, generics, class_info,
                     stdlib, global_types):
    for statement in statements:
        token = statement.token
        statement_handlers[type(statement)](statement, token, locals_,
                                            generics, class_info, stdlib,
                                            global_types, expected_return)


def variable(expression, token, locals_, generics, class_info, stdlib,
             global_types):
    name = expression.name.value
    try:
        return locals_[name]
    except KeyError:
        try:
            return global_types[name]
        except KeyError:
            raise exceptions.SanityException(
                "No such variable '{}'.".format(name),
                token.source, token.line, token.pos)


def field_access(expression, token, locals_, generics, class_info, stdlib,
                 global_types):
    actual = check_expression(locals_, generics, class_info, stdlib,
                              global_types, expression.lhs)
    static = False
    if not isinstance(actual, tuple):
        actual = actual, ()
        static = True
    cls_name, cls_generics = actual
    name = expression.field.value
    if cls_name in class_info:
        info = class_info[cls_name]
        try:
            return info["fields"][name]
        except KeyError:
            raise exceptions.SanityException(
                "No field '{}' on '{}'.".format(
                    name, type_str(actual)),
                token.source, token.line, token.pos)
    else:
        cls = get_stdlib_class(cls_name, stdlib, token)
        if static and (name in cls.static_fields):
            return cls.static_fields[name]
        else:
            raise exceptions.SanityException(
                "No field '{}' on '{}'.".format(
                    name, type_str(actual)),
                token.source, token.line, token.pos)


def operation_group(expression, token, locals_, generics, class_info, stdlib,
                    global_types):
    return check_expression(locals_, generics, class_info, stdlib, global_types,
                            expression.operation)


def cast(expression, token, locals_, generics, class_info, stdlib,
         global_types):
    check_expression(locals_, generics, class_info, stdlib, global_types,
                     expression.target)
    return type_from_node(expression.type, class_info, stdlib, generics)


def ternary_expression(expression, token, locals_, generics, class_info, stdlib,
                       global_types):
    check_expression(locals_, generics, class_info, stdlib, global_types,
                     expression.lhs, ("boolean", ()))
    true = check_expression(locals_, generics, class_info, stdlib, global_types,
                            expression.true_case)
    false = check_expression(locals_, generics, class_info, stdlib,
                             global_types, expression.false_case)
    if true != false:
        raise exceptions.SanityException(
            "Both possibilities in a ternary operator should match. "
            "Got '{}' and '{}'.".format(
                type_str(true), type_str(false)),
            token.source, token.line, token.pos)
    else:
        return true


expression_handlers = {
    mjast.ObjectConstruction: object_construction,
    mjast.Variable: variable,
    mjast.PrefixOperation: prefix_operation,
    mjast.PostfixOperation: postfix_operation,
    mjast.InfixOperation: infix_operation,
    mjast.MethodCall: method_call,
    mjast.StringLiteral: lambda *args: ("java.lang.String", ()),
    mjast.NumberLiteral: lambda *args: ("int", ()),
    mjast.BooleanLiteral: lambda *args: ("boolean", ()),
    mjast.DecimalLiteral: lambda *args: ("float", ()),
    mjast.NullLiteral: lambda *args: ("java.lang.Object", ()),
    mjast.FieldAccess: field_access,
    mjast.OperationGroup: operation_group,
    mjast.TernaryOperation: ternary_expression,
    mjast.Cast: cast,
}


def check_expression(locals_, generics, class_info, stdlib, global_types,
                     expression, expected=None):
    token = expression.token
    actual = expression_handlers[type(expression)](expression, token, locals_,
                                                   generics, class_info, stdlib,
                                                   global_types)
    if expected:
        type_check(actual, expected, generics, class_info, stdlib, token)
    else:
        return actual


def check_arguments(parameters, arguments, generics, class_info, stdlib):
    if len(parameters) != len(arguments):
        return False
    for p, a in zip(parameters, arguments):
        if not type_check(a, p, generics, class_info, stdlib):
            return False
    return True


def type_from_node(node, class_info=None, stdlib=None, generics=None):
    if not node.type:
        return None, ()
    type_ = node.type.value, tuple(type_from_node(
        g, class_info, stdlib, generics) for g in node.generics)
    if class_info is not None and stdlib is not None:
        valid_type(type_, class_info, stdlib, node.token,
                   generics if generics else ())
    return type_


def type_str(type_):
    type_, generics = type_
    if type_ is None:
        return "void"
    if generics:
        return "{}<{}>".format(type_,
                               ", ".join(type_str(g) for g in generics))
    else:
        return "{}".format(type_)


def valid_type(type_, class_info, stdlib, token, generics):
    name, type_generics = type_
    if name in generics:
        return
    if name in class_info:
        expected = class_info[name]["generics"]
    elif name in mjast.primitive_types:
        return
    else:
        expected = [(g, ())
                    for g in get_stdlib_class(name, stdlib, token).generics]
    if len(type_generics) != len(expected):
        raise exceptions.SanityException(
            "The wrong number of generics was given ({} given, {} "
            "needed).".format(len(type_generics), len(expected)),
            token.source, token.line, token.pos)


def type_check(actual, expected, generics, class_info, stdlib, token=None):
    if actual[0] is None or expected[0] is None:
        if actual[0] is None and expected[0] is None:
            return True
        elif token:
            raise exceptions.SanityException(
                "'{}' type expected, got '{}'.".format(
                    type_str(expected), type_str(actual)),
                token.source, token.line, token.pos)
        else:
            return False
    actual_type, actual_generics = actual
    expected_type, expected_generics = expected
    if not expected_type in resolve_mro(actual, generics, class_info,
                                        stdlib, token, no_generics=True):
        if not token:
            return False
        else:
            raise exceptions.SanityException(
                "'{}' type expected, got '{}'.".format(
                    type_str(expected), type_str(actual)),
                token.source, token.line, token.pos)
    if expected_generics:
        if len(actual_generics) != len(expected_generics):
            raise exceptions.SanityException(
                "The wrong number of generics was given ({} given, {} "
                "needed).".format(len(actual_generics), len(expected_generics)),
                token.source, token.line, token.pos)
        for a, e in zip(actual_generics, expected_generics):
            if not type_check(a, e, generics, class_info, stdlib, token):
                return False
    return True


def resolve_mro(type_, generics, class_info, stdlib, token, no_generics=False):
    type_, gs = type_
    if type_ in generics:
        base = "java.lang.Object", ()
    elif type_ in class_info:
        base = class_info[type_]["base"]
    elif type_ in mjast.primitive_types:
        base = "java.lang.Object", ()
    else:
        base = get_stdlib_class(type_, stdlib, token).base
    if no_generics:
        yield type_
    else:
        yield type_, gs
    if base:
        yield from resolve_mro(base, generics, class_info, stdlib, token,
                               no_generics)


def get_stdlib_class(type_, stdlib, token):
    parts = type_.split(".")
    final = parts.pop()
    current = stdlib
    for part in parts:
        current = current[part].children
    try:
        return current[final]
    except KeyError:
        raise exceptions.SanityException("No class found '{}'.".format(type_),
                                         token.source, token.line, token.pos)


def expand_all_names(node, types, generics):
    for subnode in node:
        if isinstance(subnode, mjast.Type):
            expand_name(subnode, types, generics)


def expand_name(node, types, generics):
    if node.type:
        value = node.type.value
        try:
            node.type.value = types[value]
        except KeyError:
            if not value in generics:
                token = node.type
                raise exceptions.TypeException(
                    value, token.source, token.line, token.pos)
    for g in node.generics:
        expand_name(g, types, generics)


def resolve_types(program, stdlib):
    types = {name: impl for name, impl in mjast.primitive_types.items()}

    # Deal with java.lang.* auto-import.
    _star_resolve(stdlib, ["java", "lang"], types)

    # Deal with imports.
    for imp in program.imports:
        parts = [name.value for name in imp.name]
        final = parts.pop()
        if final == "*":
            _star_resolve(stdlib, parts, types)
        else:
            types[final] = ".".join(parts + [final])

    # Deal with classes defined in the program.
    for cls in program.classes:
        types[cls.name.value] = cls.name.value

    # Deal with FQNs
    _fqn_resolve(stdlib["java"], types)

    return types


def _fqn_resolve(current, types):
    for name, cls in current.children.items():
        fqn = "{}.{}".format(cls.parent, name)
        types[fqn] = fqn
        if hasattr(cls, "children"):
            _fqn_resolve(cls, types)


def _star_resolve(stdlib, parts, types):
    current = stdlib
    for part in parts:
        current = current[part].children
    for name, cls in current.items():
        types[name] = "{}.{}".format(cls.parent, name)


if __name__ == "__main__":
    import argparse

    args = argparse.ArgumentParser(
        description='Interpret Middleweight Java Code.')
    args.add_argument('file', metavar='FILE', type=argparse.FileType('r'),
                      default=sys.stdin, help='The source code to interpret.')

    args = args.parse_args()
    target = args.file.name or "<stdin>"
    source = args.file
    program = parse_handling_errors(source)
    analyse_handling_errors(program)
    print('"{}" is semantically valid.'.format(target))
    print("\n".join(program.tree()))
    sys.exit(0)
