#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Classes for handling types/classes."""

from exceptions import ExecutionException
import interpreter
import abc
import mjast


class Method(metaclass=abc.ABCMeta):
    def __init__(self, cls, name, static, generics, return_type, parameters):
        self.cls = cls
        self.name = name
        self.static = static
        self.generics = generics
        self.return_type = return_type
        self.parameters = parameters
        self._typed = False

    def fits(self, name, args, static):
        if not self._typed:
            self.type()
        if not self.name == name or self.static not in (True, static):
            return False
        #Type debugging.
        #print([(self.name, name, a.type, p, a.type.check(p))
        #      for a, (_, p) in zip(args, self.parameters)])
        return (len(args) == len(self.parameters)
                and all(a.type.check(p)
                        for a, (_, p) in zip(args, self.parameters)))

    def run(self, *args, call):
        if not self._typed:
            self.type()
        return self._run(*args, call=call)

    @abc.abstractmethod
    def _run(self, cls, instance, args, context, *, call):
        pass

    @abc.abstractmethod
    def type(self):
        pass

    def __repr__(self):
        return "[Method: {}]".format(self.name)


class NativeMethod(Method):
    def __init__(self, cls, node):
        self.cls = cls
        generics = [g.type.value for g in node.generics]
        parameters = [(arg.name.value, arg.type) for arg in node.parameters]
        if node.type.type is not None:
            return_type = node.type
        else:
            return_type = None
        super().__init__(cls, node.name.value, node.static, generics,
                         return_type, parameters)
        self.scope = interpreter.Scope("{}.{}".format(
            self.cls.name, self.name), self.cls.scope,
            {name: Generic(name) for name in self.generics})
        self._statements = node.statements
        self._token = node.token

    def type(self):
        self._typed = True
        self.parameters = [(value, self.scope.type(type_,
                                                   resolve_generics=True))
                           for value, type_ in self.parameters]
        self.return_type = (self.scope.type(self.return_type,
                                            resolve_generics=True)
                            if self.return_type is not None else None)

    def _run(self, cls, instance, args, context, *, call):
        variables = {param: arg
                     for arg, (param, _) in zip(args, self.parameters)}
        types = dict(Generic.fill_generic(
            [pt for _, pt in self.parameters], [arg.type for arg in args]))
        if instance:
            scope = instance.scope
        else:
            scope = cls.scope
        description = self.description
        context = interpreter.Scope(description, scope, types, variables,
                                    stack=scope.stack)
        context.stack.enter(interpreter.Frame(description, call))
        try:
            value = interpreter.execute(self._statements, context)
        except Return as e:
            value = e.value
        scope.stack.exit()
        return value

    @property
    def description(self):
        params = ["{} {}".format(type_, name)
                  for name, type_ in self.parameters]
        return "{}.{}({})".format(self.cls.name, self.name, ", ".join(params))


class NativeConstructor(NativeMethod):
    def __init__(self, cls, node):
        Method.__init__(self, cls, cls.name, False, {}, None,
                        [(arg.name.value, arg.type)
                         for arg in node.parameters])
        self.cls = cls
        self.token = node.token
        self._super_arguments = node.super_arguments
        self._statements = node.statements

    def type(self):
        self._typed = True
        self.parameters = [(value, self.cls.scope.type(type_))
                           for value, type_ in self.parameters]

    def _run(self, cls, instance, args, context, *, call):
        variables = {param: arg
                     for arg, (param, _) in zip(args, self.parameters)}
        generic_classes = dict(Generic.fill_generic(
            [pt for _, pt in self.parameters], [arg.type for arg in args]))
        scope = instance.scope
        description = self.description
        context = interpreter.Scope(description, scope,
                                    generic_classes, variables)
        context.stack.enter(interpreter.Frame(description, call))
        if cls.base:
            if self._super_arguments:
                arguments = [interpreter.evaluate(argument, scope)
                             for argument in self._super_arguments]
                cls.base.run_constructor(instance, arguments,
                                         context, call=call)
            else:
                cls.base.run_constructor(instance, (), scope, call=call)
        try:
            interpreter.execute(self._statements, context)
        except Return:
            pass
        scope.stack.exit()

    @property
    def description(self):
        return "{}({})".format(self.cls.name, ", ".join(
            ["{} {}".format(type_, name) for name, type_ in self.parameters]))


class Instance:
    """A class instance during execution."""

    def __init__(self, cls, arguments, context, *, call):
        self.cls = cls
        self.scope = self.make_scope(context)
        self.internal = {}
        cls.run_constructor(self, arguments, self.scope, call=call)

    def run_method(self, name, args, context, *, call):
        return self.cls.run_method(name, args, self.scope, instance=self,
                                   call=call)

    def make_scope(self, context):
        fields = {name: interpreter.Variable(type_)
                  for type_, name in self.cls.fields}
        fields["this"] = interpreter.Variable(self.cls, self)
        return interpreter.Scope(
            "{}()".format(self.cls),
            None,
            context.top.types,
            fields,
            stack=context.stack
        )

    def __repr__(self):
        return "~{}".format(self.cls)


class Class:
    name = None
    parent = None
    base = "java.lang.Object", ()
    generics = []
    fields = set()
    constructors = set()
    methods = set()
    static = False

    default_value = None

    _constructor_class = NativeConstructor
    _method_class = NativeMethod
    _instance_class = Instance

    def __init__(self, scope, generics=None, static=False):
        self.specified = generics if generics is not None else ()
        if not static:
            if len(self.specified) != len(self.generics):
                raise ValueError(
                    "The wrong number of generics was given ({} given,"
                    " {} needed).".format(len(self.specified),
                                          len(self.generics)))
            types = {generic: specified for generic, specified in
                     zip(self.generics, self.specified)}
            types.update(scope.top.types)
            self.scope = interpreter.Scope(
                self.name, None, types, stack=scope.stack)
        else:
            self.scope = interpreter.Scope(self.name, None, scope.top.types,
                                           stack=scope.stack)
        self.generics = self.specified
        self.base = self.scope.type(self.base)
        self.mro = list(self._mro())
        self.parent = self.scope.type(self.parent)
        if not static:
            self.fields = {(self.scope.type(type_), name)
                           for type_, name in self.fields}
            self.constructors = {self._constructor_class(self, constructor)
                                 for constructor in self.constructors}
            self.methods = {self._method_class(self, method)
                            for method in self.methods}
        if static:
            self.methods = {self._method_class(self, method)
                            for method in self.methods if method.static}

    @classmethod
    def native_class(cls, node):
        name = node.name.value
        new = type(name, (cls, ), {
            "name": name,
            "base": node.base,
            "generics": [name for name in
                         [g.type.value for g in node.generics]],
            "fields": {(field.type, field.name.value) for field in node.fields},
            "constructors": set(node.constructors),
            "methods": set(node.methods),
        })
        return new

    def instance(self, args, context, *, call):
        return self._instance_class(self, args, context, call=call)

    def run_method(self, name, args, context, instance=None, *, call):
        static = instance is None
        matches = {method for method in self.methods
                   if method.fits(name, args, static)}
        if len(matches) > 1:
            raise ExecutionException(
                "Ambiguous method arguments for {!r} - ({}) fits ({}).".format(
                    name, ", ".join([arg.type.name for arg in args]),
                    "; ".join([", ".join([str(param.type.name)
                                          for param in method.parameters])
                               for method in matches])), context.stack,
                call.token.source, call.token.line, call.token.pos)
        elif not matches:
            if self.base:
                return self.base.run_method(name, args, context, instance,
                                            call=call)
            else:
                raise ExecutionException(
                    "No {} method {!r} with arguments ({}).".format(
                        "static " if static else "", name,
                        ", ".join([str(arg.type) for arg in args])),
                    context.stack, call.token.source, call.token.line,
                    call.token.pos)
        else:
            method, = matches
        if method.static:
            instance = None
        return method.run(self, instance, args, context, call=call)

    def run_constructor(self, instance, args, context, *, call):
        if not len(self.constructors) and not args:
            if self.base:
                self.base.run_constructor(instance, (), context, call=call)
            return
        matches = {constructor for constructor in self.constructors
                   if constructor.fits(self.name, args, False)}
        if len(matches) > 1:
            raise ExecutionException(
                "Ambiguous constructor arguments for ({}) fits ({}).".format(
                    name, ", ".join([arg.type.name for arg in args]),
                    "; ".join([", ".join([str(param.type.name)
                                          for param in method.parameters])
                               for method in matches])), context.stack,
                call.token.source, call.token.line, call.token.pos)
        elif not matches:
            gnames = ", ".join(g.full_name for g in self.generics)
            raise ExecutionException(
                "No constructor for {}{} with arguments ({}).".format(
                    self.full_name,
                    "<{}>".format(gnames) if gnames else "",
                    ", ".join([str(arg.type) for arg in args])),
                context.stack, call.token.source, call.token.line,
                call.token.pos)
        else:
            constructor, = matches
        constructor.run(self, instance, args, context, call=call)

    def _mro(self):
        yield type(self)
        if self.base:
            yield from self.base._mro()

    def check(self, base):
        if isinstance(base, Generic):
            if not base.type:
                return True
            else:
                return self.check(base.type)
        return (self.is_subclass_of(base) and
                all(sg.check(bg)
                    for sg, bg in zip(self.generics, base.generics)))

    def is_subclass_of(self, base):
        return type(base) in self.mro

    @property
    def full_name(self):
        if self.parent:
            if not hasattr(self.parent, "full_name"):
                return "(?.){}.{}".format(self.parent, self.name)
            return "{}.{}".format(self.parent.full_name, self.name)
        else:
            return self.name

    def __eq__(self, other):
        return self.name == other.name and self.parent == other.parent

    def __hash__(self):
        return hash(self.name) + hash(self.parent)

    def __repr__(self):
        generics = ", ".join(str(t) for t in self.generics)
        return "{}{}".format(
            self.full_name, "<{}>".format(generics) if generics else "")


class Type(Class):
    def __init__(self, scope, generics=None):
        self.base = None
        self.mro = [self]


class Object(Class):
    name = "Object"
    parent = "java.lang"
    base = None
    generics = set()
    fields = set()
    constructors = set()
    methods = set()

    def __init__(self, scope, generics=None):
        pass


primitive_types = {name: type(name, (Type, ), {
    "name": name,
    "parent": None,
    "base": "java.lang.Object",
    "default_value": value,
}) for name, value in mjast.default_primitive_values.items()}


class Generic:
    def __init__(self, name, type_=None):
        self.name = name
        self.type = type_

    @classmethod
    def fill_generic(cls, generics, specifics):
        for g, s in zip(generics, specifics):
            if isinstance(g, cls):
                yield g.name, s
            else:
                yield from cls.fill_generic(g.generics, s.generics)

    @classmethod
    def apply(cls, *generics):
        def decorate(func):
            func.generics = generics
            return func
        return decorate

    def __eq__(self, other):
        if hasattr(other, "name"):
            return self.name == other.name

    def __hash__(self):
        return hash(self.name)

    def __repr__(self):
        return "{}({})".format(self.name, self.type if self.type else "")


class Return(Exception):
    def __init__(self, value=None):
        self.value = value
