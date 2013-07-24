# Montyweight Java - A Middleweight Java Interpreter In Python

A complete parser and interpreter for a subset of the Java language, written
in Python. This was produced as a deliverable for my final year project for 
my degree in Computer Science from the University of Leicester - it is barely
commented, and was written under deadlines without much aim for particularly 
excellent code. It was a project aimed at being interesting over all else - 
performance is no doubt abysmal.

## License

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

## Requirements

 - [Python 3.3](http://www.python.org/download/releases/3.3.0/)

## Included

 - Tokenizer (Lexical analysis).
 - Parser (Syntax analysis).
 - Semantic Analyser
 - Interpreter
 - Graphical Debugger
 - Compiler (Targeting Python bytecode)

### Files

 - __init__.py
 - classes.py
 - compiler.py
 - debug.py
 - exceptions.py
 - interpreter.py
 - library.py
 - LICENSE
 - parser.py
 - README.md
 - semantics.py
 - tokenizer.py
 - examples
   - Generics.java
   - Inheritance.java
   - MergeSorter.java
   - OperatorPrecedence.java
   - Simple.java
 - mjast
   - __init__.py
   - components.py
   - core.py
   - expressions.py
   - node.py
   - primitive_types.py
   - promotable.py
   - statements.py
 - stdlib
   - __init__.py
   - io.py
   - lang.py
   - util.py

## Support

### Language Support

The interpreter supports the full Middlewieght Java language, as defined in the
the paper [MJ: An imperative core calculus for Java and Java with
effects](http://www.cl.cam.ac.uk/techreports/UCAM-CL-TR-563.pdf), and some
extensions, listed below:

 - `for` loops.
 - `while` loops.
 - Operators.
 - Multiple constructors.
 - Empty blocks.
 - Declaration with assignment.
 - `import` statements (albeit with different behaviour to full Java).
 - Using generic types/methods.
 - `if` blocks without `else` blocks.
 - `else if` blocks.
 - Implied `extends Object`.
 - Empty `super()` can be left out.
 - Static classes & methods.
 - Strings & string literals.
 - Brackets for operation grouping.

### Library Support

Most of the Java standard library is unsupported. Some small parts have been
implemented, and these are listed below:

 - `lang.Integer`
 - `lang.String`
 - `lang.System.out`
 - `util.List`
 - `io.PrintStream`

Note that all of these implementations are partial (even skeletal).

Do note, however, that the interpreter does include a full system to allow the
implementation of Python libraries for use in the interpreted code. This would
allow full implementation of the standard library, given the time and effort.

## Usage

### As a command line application.

The interpreter can be used simply as a command line application. Given
Python 3.3 is installed, simply run `python interpreter.py some_code.java`
(on some platforms, it may be necessary to use `python3` to differentiate
between Python 2.x and 3.x, which can be installed simultaneously. On Unix
platforms, `./interpreter.py some_code.java` should also work, given the code
is set as executable.

### Debugger

Also included is a graphical debugger that allows stepping through code, and
viewing the execution state. This is `debug.py`.

### Compiler

The compiler should work with `python compiler.py some_code.java` - note that
it only handles an extremely small subset of the language.

### As a library.

The interpreter can be used as a library from other software, and the parser
could also be used independantly to produce an abstract syntax tree that could
be worked with as desired.

## Author

Written by Gareth Latty <gareth@lattyware.co.uk> as a deliverable for CO3016 
Computer Science Project, part of a Computer Science degree at the Unversity
of Leicester.
