#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""A (partial) implementation of `java.util`."""

from library import LibClass, constructor, method


class util(LibClass):
    name = "util"
    parent = "java"
    static = True

    class List(LibClass):
        name = "List"
        parent = "java.util"
        generics = ["E"]

        @constructor()
        def const(self, instance):
            instance.internal["list"] = []

        @method()
        def add(self, instance, item: ("E", ())) -> None:
            instance.internal["list"].append(item)

        @method()
        def clear(self, instance) -> None:
            instance.internal["list"].clear()

        @method()
        def contains(self, instance, o: ("java.lang.Object", ())
                     ) -> ("boolean", ()):
            return o in instance.internal["list"]

        @method()
        def get(self, instance, index: ("int", ())) -> ("E", ()):
            return instance.internal["list"][index.value].value

        @method()
        def size(self, instance) -> ("int", ()):
            return len(instance.internal["list"])

        @method()
        def set(self, instance, index: ("int", ()), value: ("E", ())
                ) -> ("E", ()):
            old = instance.internal["list"][index.value].value
            instance.internal["list"][index.value] = value
            return old

        @method()
        def subList(self, instance, fromIndex: ("int", ()), toIndex: ("int", ())
                    ) -> ("java.util.List", (("E", ()), )):
            new = util.List(generics=self.generics)
            new.list = instance.internal["list"][fromIndex.value:toIndex.value]
            return new

        @method()
        def remove(self, instance, index: ("int", ())) -> ("E", ()):
            return instance.internal["list"].pop(index.value)

        def _debug(self, instance):
            for i, v in enumerate(instance.internal["list"]):
                yield ".get({})".format(i), v
