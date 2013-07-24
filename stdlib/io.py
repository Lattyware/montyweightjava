#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""A (partial) implementation of `java.io`."""

from library import LibClass, method


class io(LibClass):
    name = "io"
    parent = "java"
    static = True
    base = None

    class PrintStream(LibClass):
        name = "PrintStream"
        parent = "java.io"

        @method()
        def println(self, instance, x: ("java.lang.String", ())) -> None:
            print(x.value)

        @method()
        def print(self, instance, x: ("java.lang.String", ())) -> None:
            print(x.value, end="")
