#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""A simple debugger, allowing stepping through code.."""

import sys
import interpreter
import threading
import argparse
from tkinter import *
from tkinter import ttk

import sematics

current_scope = None
current_statement = None
pause = threading.Event()
target = None


class RepeatedTimer(object):
    def __init__(self, interval, function, *args, **kwargs):
        self._timer = None
        self.interval = interval
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.is_running = False

    def _run(self):
        self.is_running = False
        self.start()
        self.function(*self.args, **self.kwargs)

    def start(self):
        if not self.is_running:
            self._timer = threading.Timer(self.interval, self._run)
            self._timer.start()
            self.is_running = True

    def stop(self):
        self._timer.cancel()
        self.is_running = False


def execute(statements, scope):
    for statement in statements:
        debug(statement, scope)
        interpreter._execute[type(statement)](statement, scope)


def debug(node, scope):
    global current_scope
    global current_statement
    global target
    current_scope = scope
    current_statement = node
    if target is None or current_scope == target:
        update()
        pause.clear()
        pause.wait()


def exit_():
    root.destroy()
    sys.exit(0)


def step(*args):
    global target
    target = None
    pause.set()


def step_over(*args):
    global target
    target = current_scope
    pause.set()


def step_out(*args):
    global target
    target = current_scope.outer
    pause.set()


auto = RepeatedTimer(0.1, step)


def update():
    tree.delete(*tree.get_children())
    code.config(state=NORMAL)
    left = current_statement.left
    right = current_statement.right
    start = "{}.{}".format(left.line, left.pos - 1)
    end = "{}.{} + {} chars".format(right.line, right.pos - 1, right.length)
    code.see(end)
    code.see(start)
    code.tag_remove("current", "0.0", "end")
    code.tag_add("current", start, end)
    code.config(state=DISABLED)
    tree_from_state(current_scope)


def clear():
    tree.delete(*tree.get_children())
    code.config(state=NORMAL)
    code.tag_remove("current", "0.0", "end")
    code.config(state=DISABLED)


def tree_from_state(scope):
    variables = tree.insert("", "end", text="Variables")
    seen = set()
    while scope is not None:
        tree.see(variables)
        for name, value in scope.variables.items():
            if not name in seen:
                seen.add(name)
                id_ = tree.insert(variables, "end", text=name,
                                  values=(value.type, value.value))
                tree.see(id_)
                add_child_nodes(value.value, id_)
        scope = scope.outer
    tree.see(variables)


def add_child_nodes(item, parent):
    if isinstance(item, interpreter.classes.Instance):
        if isinstance(item, interpreter.library.LibInstance):
            for name, value in item.cls._debug(item):
                id_ = tree.insert(parent, "end", text=name,
                                  values=(value.type, value.value))
                add_child_nodes(value.value, id_)
        else:
            for name, value in item.scope.variables.items():
                if name != "this":
                    id_ = tree.insert(parent, "end", text=name,
                                      values=(value.type, value.value))
                    tree.see(id_)
                    add_child_nodes(value.value, id_)


class OutCatcher:
    def write(self, text):
        output.config(state=NORMAL)
        output.insert("end", text)
        output.config(state=DISABLED)

    def flush(self):
        pass


class ErrCatcher:
    def write(self, text):
        output.config(state=NORMAL)
        output.insert("end", text, "error")
        output.config(state=DISABLED)

    def flush(self):
        pass


root = Tk()
root.title("Middleweight Java Debugger")
root.columnconfigure(0, weight=1)
root.rowconfigure(0, weight=1)
root.protocol('WM_DELETE_WINDOW', exit_)

frame = ttk.Frame(root, padding="2 2 2 2")
frame.grid(column=0, row=0, sticky=(N, S, E, W))
frame.columnconfigure(0, weight=1)
frame.columnconfigure(1, weight=1)
frame.columnconfigure(2, weight=1)
frame.columnconfigure(3, weight=1)
frame.columnconfigure(4, weight=1)
frame.columnconfigure(6, weight=3)
frame.rowconfigure(0, weight=2)
frame.rowconfigure(1, weight=1)
frame.rowconfigure(2, weight=0)

ttk.Button(frame, text="Step Over",
           command=step_over).grid(column=0, row=2, sticky=(N, S, E, W))
ttk.Button(frame, text="Step Into",
           command=step).grid(column=1, row=2, sticky=(N, S, E, W))
ttk.Button(frame, text="Step Out",
           command=step_out).grid(column=2, row=2, sticky=(N, S, E, W))
ttk.Button(frame, text="Play",
           command=auto.start).grid(column=3, row=2, sticky=(N, S, E, W))
ttk.Button(frame, text="Stop",
           command=auto.stop).grid(column=4, row=2, sticky=(N, S, E, W))

tree = ttk.Treeview(frame, columns=("Type", "Value"))
tree.heading("#0", text="Name")
tree.heading("Type", text="Type")
tree.heading("Value", text="Value")
tree.grid(column=0, row=0, columnspan=5, sticky=(N, S, E, W))

code = Text(frame)
code.grid(column=6, row=0, rowspan=3, sticky=(N, S, E, W))
code.tag_configure("current", background="yellow", relief="raised")

output = Text(frame, height=10)
output.grid(column=0, row=1, columnspan=5, sticky=(N, S, E, W))
output.tag_configure("error", foreground="red")

ts = ttk.Scrollbar(frame, orient=VERTICAL, command=tree.yview)
ts.grid(column=5, row=0, sticky=(N, S))
cs = ttk.Scrollbar(frame, orient=VERTICAL, command=code.yview)
cs.grid(column=7, row=0, rowspan=2, sticky=(N, S))
os = ttk.Scrollbar(frame, orient=VERTICAL, command=output.yview)
os.grid(column=5, row=1, sticky=(N, S))

tree.configure(yscrollcommand=ts.set)
code.configure(yscrollcommand=cs.set)
output.configure(yscrollcommand=os.set)

ttk.Sizegrip(frame).grid(column=7, row=2, sticky=(S, E))

for child in frame.winfo_children():
    child.grid_configure(padx=2, pady=2)

root.lift()

args = argparse.ArgumentParser(
    description='Debugger for Middleweight Java Code.')
args.add_argument('file', metavar='FILE', type=argparse.FileType('r'),
                  default=sys.stdin, help='The source code to debug.')

args = args.parse_args()

interpreter.execute = execute

with open(args.file.name) as file:
    code.insert("1.0", file.read())
code.config(state=DISABLED)
output.config(state=DISABLED)
program = interpreter.parse_handling_errors(args.file)
sematics.analyse_handling_errors(program)


def run():
    sys.stdout = OutCatcher()
    #sys.stderr = ErrCatcher()
    if program:
        try:
            interpreter.interpret(program, args.file.name)
        except interpreter.InterpreterException as e:
            e.print_traceback()
            update()
        clear()

threading.Thread(target=run, name="MWJ Interpreter", daemon=True).start()

root.mainloop()
