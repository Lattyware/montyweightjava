#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Base AST node implementation."""

from abc import ABCMeta, abstractmethod
import itertools

import mjast
import tokenizer


DEBUG = False


class Node:
    """An ABC for all program nodes."""
    __metaclass__ = ABCMeta

    def __init__(self, code):
        self.code = code
        if DEBUG:
            print("--> " + type(self).__name__)
        if hasattr(self, "expression"):
            if not hasattr(self, "_parts"):
                self._parts = [p for p in self.expression if hasattr(p, "name")]
                self._parts = ([p.name for p in self._parts if not p.many],
                               [p.name for p in self._parts if p.many])
                single, many = self._parts
                for part in single:
                    if not hasattr(self, part):
                        setattr(self, part, None)
                for part in many:
                    if not hasattr(self, part):
                        setattr(self, part, [])
            self.expression = mjast.ParseExpression(self.expression)
        self.token = self.code.current
        self._last = self._parse()
        self._last = self._last if self._last else self

    @property
    def right(self):
        if isinstance(self._last, tokenizer.Token):
            return self._last
        return self._last.right if self._last.right else self._last.token

    @property
    def left(self):
        return self.lhs.left if hasattr(self, "lhs") else self.token

    def _parse(self):
        return self.expression.parse(self)

    def _indent(self, lines):
        return ["│ " + line for line in lines]

    def _get_parts(self):
        fields, many_fields = self._parts
        fields = [(name, getattr(self, name)
                   if getattr(self, name) is not None else "None")
                  for name in fields]
        many_fields = [(name, getattr(self, name)) for name in many_fields]
        return fields, many_fields

    @abstractmethod
    def tree(self):
        fields, many_fields = self._get_parts()
        if many_fields:
            tree = ["┌{}".format(type(self).__name__)]
            tree.extend(
                "├─{}: {}".format(name, value) for name, value in fields)
            for name, items in many_fields:
                tree.append("├─{}:".format(name))
                tree.extend(itertools.chain.from_iterable(
                    self._indent(item.tree()) for item in items))
            tree.append("└────")
        else:
            return [repr(self)]
        return tree

    def __iter__(self):
        single, many = self._parts
        for part in single:
            part = getattr(self, part)
            if isinstance(part, Node):
                yield part
                yield from part
        for parts in many:
            parts = getattr(self, parts)
            for part in parts:
                if isinstance(part, Node):
                    yield part
                    yield from part

    def __repr__(self):
        fields, many_fields = self._get_parts()
        values = ""
        if fields:
            values = " " + " ".join("{}: {}".format(name, value)
                                    for name, value in fields)
        if many_fields:
            values += " " + " ".join("{}: {}".format(name,
                                                     ", ".join(str(value)
                                                               for value in
                                                               values))
                for name, values in many_fields)
        return "[{}{}]".format(type(self).__name__, values)
