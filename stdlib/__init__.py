#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""All standard library providing modules must be imported here."""

from library import LibClass

from stdlib.lang import lang
from stdlib.io import io
from stdlib.util import util


class java(LibClass):
    name = "java"
    static = True
    base = None

    lang = lang
    io = io
    util = util

standard_library = [java]
