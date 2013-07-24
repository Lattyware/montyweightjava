#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This module provides an easy way to make Python extension libraries. These can
be loaded in and used from MWJ code as though they were pure MWJ libraries.
"""

import inspect
from classes import Method, Class, Instance
import interpreter


def load_standard_library():
    import stdlib
    return {cls.name: cls for cls in stdlib.standard_library}


def method(static=False):
    def decorate(obj):
        signature = inspect.signature(obj)
        return_type = signature.return_annotation
        params = iter(signature.parameters.values())
        next(params)  # Skip self/cls.
        if not static:
            next(params)  # Skip instance.
        params = list(params)
        for param in params:
            if param.annotation is inspect.Parameter.empty:
                raise AttributeError("STDLib functions must have "
                                     "annotations to give the parameter "
                                     "types.")
        if return_type is inspect.Signature.empty:
            raise AttributeError("STDLib functions must have an "
                                 "annotation to give the return type.")
        obj.types = [param.annotation for param in params]
        obj.static = static
        obj.method = True
        obj.return_type = return_type
        return obj
    return decorate


def constructor():
    def decorate(obj):
        signature = inspect.signature(obj)
        params = iter(signature.parameters.values())
        next(params)  # Skip self/cls.
        next(params)  # Skip instance.
        params = list(params)
        for param in params:
            if param.annotation is inspect.Parameter.empty:
                raise AttributeError("STDLib functions must have "
                                     "annotations to give the parameter "
                                     "types.")
        obj.types = [param.annotation for param in params]
        obj.constructor = True
        obj.static = False
        return obj
    return decorate


class LibMethod(Method):
    def __init__(self, cls, func):
        static = func.static
        generics = func.generics if hasattr(func, "generics") else ()
        self.scope = cls.scope
        signature = inspect.signature(func)
        params = iter(signature.parameters.values())
        if not static:
            next(params)
        self.parameters = [(param.name, param.annotation) for param in params]
        return_type = signature.return_annotation
        self.return_type = (return_type
                            if return_type is not signature.empty else None)
        self._func = func
        name = (func.__name__
                if not hasattr(self._func, "constructor") else cls.name)
        super().__init__(cls, name, static, generics, return_type,
                         self.parameters)

    def type(self):
        self._typed = True
        self.parameters = [(name, self.scope.type(type_, resolve_generics=True))
                           for name, type_ in self.parameters]
        if not hasattr(self._func, "constructor"):
            self.return_type = (self.scope.type(self.return_type,
                                                resolve_generics=True)
                                if self.return_type is not None else None)

    def _run(self, cls, instance, args, context, *, call):
        if instance is not None:
            args = (instance, ) + tuple(args)
        if not hasattr(self._func, "constructor"):
            return interpreter.Variable(self.return_type, self._func(*args))
        else:
            self._func(*args)


class LibClassMeta(type):
    def __new__(mcs, name, bases, attributes):
        attributes["methods"] = {func.__name__
                                 for func in attributes.values() if
                                 (inspect.isfunction(func) and
                                 hasattr(func, "method"))}
        attributes["constructors"] = {func.__name__
                                      for func in attributes.values() if
                                      (inspect.isfunction(func) and
                                       hasattr(func, "constructor"))}
        attributes["children"] = {cls.__name__: cls
                                  for cls in attributes.values() if
                                  (inspect.isclass(cls) and
                                   issubclass(cls, Class) and
                                   not name.startswith("_"))}
        return super().__new__(mcs, name, bases, attributes)


class LibInstance(Instance):
    """A class instance from a Python library during execution."""

    def __init__(self, cls, arguments, context, *, call):
        self.cls = cls
        self.internal = {}
        self.scope = self.make_scope(context)
        cls.run_constructor(self, arguments, self.scope, call=call)

    def run_method(self, name, args, context, instance=None, *, call):
        return self.cls.run_method(name, args, self.scope, call=call,
                                   instance=self)

    def __repr__(self):
        if hasattr(self.cls, "debug"):
            return self.cls.debug(self)
        return repr(self.cls)


class LibClass(Class, metaclass=LibClassMeta):
    """A base class for all classes to be exposed to MWJ, providing some
    base functionality. Note that you need to use the expose decorator on such
    classes, and all child functions that need to be accessible."""

    _constructor_class = LibMethod
    _method_class = LibMethod
    _instance_class = LibInstance

    def __init__(self, *args, **kwargs):
        self.methods = {getattr(self, m) for m in self.methods}
        self.constructors = {getattr(self, c) for c in self.constructors}
        self.static_fields = {}
        super().__init__(*args, **kwargs)

