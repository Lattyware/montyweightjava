#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""A (partial) implementation of `java.lang`."""

from classes import Class, Object
from library import LibClass, method

from stdlib.io import io


class lang(LibClass):
    name = "lang"
    parent = "java"
    static = True
    base = None

    Object = Object

    class String(Class):
        name = "String"
        parent = "java.lang"

    class Integer(LibClass):
        name = "Integer"
        parent = "java.lang"
        static = True

        @method(static=True)
        def toString(self, x: ("int", ())) -> ("java.lang.String", ()):
            return str(x.value)

        @method(static=True)
        def parseInt(self, x: ("java.lang.String", ())) -> ("int", ()):
            return int(x.value)

    class System(LibClass):
        name = "System"
        parent = "java.lang"
        static = True
        static_fields = {"out": ("java.io.PrintStream", ())}

        def __init__(self, scope, *args, **kwargs):
            super().__init__(scope, *args, **kwargs)
            self.out = io.PrintStream(scope).instance((), scope, call=None)
