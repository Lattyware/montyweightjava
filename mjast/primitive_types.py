#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""The primitive types for Java."""

primitive_types = {
    "int": "int",
    "float": "float",
    "boolean": "boolean",
    # Python handles integers as longs (and auto-promotes to bignumbers) and
    # floats as doubles, so we actually implement these all the same way.
    "byte": "int",
    "short": "int",
    "long": "int",
    "double": "float",
    #"char": "char"
}

default_primitive_values = {
    "int": 0,
    "float": 0.0,
    "boolean": False
}
