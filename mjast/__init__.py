#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Collects the Abstract Syntax Tree nodes into a single source."""

from mjast.node import Node

from mjast.components import (ParseExpression, identifier, name, keyword,
                              symbol, until, statements, parameters, arguments,
                              delegate, expression, operator, literal,
                              statement, constructors, If, EndIf, Else,
                              dotted_name, generics, type_identifier, exists,
                              keyword_using_token)

statements_ = statements  # Ugly hack here.

from mjast.statements import (Statement, NoOp, WhileLoop, ForLoop, Conditional,
                              FieldAssignment, LocalVariableDeclaration,
                              VariableAssignment, Return, Block)

statements = statements_
del statements_

from mjast.expressions import (Expression, OperationGroup, Operation,
                               PrefixOperation, PostfixOperation,
                               InfixOperation, TernaryOperation, Literal,
                               StringLiteral, NumberLiteral, DecimalLiteral,
                               NullLiteral, BooleanLiteral, Variable,
                               FieldAccess, Cast)

from mjast.promotable import (PromotableExpression, MethodCall,
                              ObjectConstruction)

from mjast.core import (Program, Class, Field, Parameter, Constructor, Method,
                        Type, Import)


from mjast.primitive_types import primitive_types, default_primitive_values

"""
$program ::== $import*
              $class*

$import ::== import $dottedname;

$dottedname ::== C[.$dottedname]?

$class ::== static? class $type [extends $type]? {
                $field*
                $constructor+
                $method*
            }

$type ::== C[<$generics>]?

$generics ::== C[, C]*

$field ::== $type F;

$constructor ::== C($parameters?) {
                      [super($arguments?);]?
                      $statement*
                  }

$parameters ::== $type P[, $type P]*

$arguments ::== $expression[, $expression]*

$method ::== static? [<$generics>]? $returntype M($parameters?) {
                 $statement*
             }

$returntype ::== void
               | $type

$statement ::== $unclosedstatement;

$rawstatement ::== while ($expression) {
                       $statement*
                   }
                 | for ($rawstatement; $expression; $rawstatement) {
                       $statement*
                   }
                 | $conditional
                 | $expression.F $assignmentoperator $expression
                 | $type L [$assignmentoperator $expression]?
                 | L $assignmentoperator $expression
                 | return $expression?
                 | {
                       $statement*
                   }
                 | $promotable

$conditional ::== if ($expression) {
                       $statement*
                  } [else $conditional]?
                | if ($expression) {
                       $statement*
                  } else {
                       $statement*
                  }

$expression ::== $base_expression
               | $base_expression$recursed_expression

$base_expression ::== ($expression)
                    | $prefixoperator $expression
                    | $literal
                    | L
                    | ($type) $expression
                    | $recursed_expression

$recursed_expression ::== $left_operator
                          .$dotted_expression

$left_operator ::== $postfixoperator
                  | $infixoperator $expression
                  | ? $expression : $expression

$dotted_expression ::== F
                      | M($arguments?)

$promotable ::== $expression.M($arguments?)
               | $expression $postfixoperator
               | new C($arguments?)

$assignmentoperator ::== = | /= | `*=` | += | -= | `|=`
                       | &= | %= | ^= | <<= | >>= | >>>=

$prefixoperator ::== ! | ~ | `++` | -- | `+` | -

$postfixoperator ::== `++` | --

$infixoperator ::== `*` | / | % | == | != | > | >= | < | <=
                  | instanceof | && | `||` | << | >> | >>>
                  | & | ^ | `|`

$literal ::== "r[^"]" | 'r[^']'
            | r[0-9]r[0-9]*.?r[0-9]*
            | true | false
            | null
"""
