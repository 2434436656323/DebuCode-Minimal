
# ============================================================
# DebuCode Minimal — интерпретатор
# Версия: 0.2
# Встроенные модули: tkinter, random, os, sys, subprocess, flask
# ============================================================

import sys
import os
import re
import json
import math
import time
import random
import subprocess
import zipfile
import io
import types
import traceback
from collections import OrderedDict

# ---- Встроенные модули (пробуем импортировать опциональные) ----
try:
    import tkinter as _tkinter_mod
    HAS_TKINTER = True
except ImportError:
    HAS_TKINTER = False

try:
    from flask import Flask as _FlaskClass
    from flask import request as _flask_request
    from flask import jsonify as _flask_jsonify
    from flask import redirect as _flask_redirect
    from flask import render_template_string as _flask_render_template_string
    HAS_FLASK = True
except ImportError:
    HAS_FLASK = False


# ============================================================
# ЛЕКСЕР
# ============================================================

class Token:
    def __init__(self, type, value, line, col):
        self.type = type
        self.value = value
        self.line = line
        self.col = col
    def __repr__(self):
        return f"Token({self.type}, {self.value!r}, line={self.line})"

KEYWORDS = {
    'if', 'elif', 'else', 'while', 'for', 'in', 'def', 'return',
    'break', 'continue', 'pass', 'and', 'or', 'not',
    'True', 'False', 'None', 'import', 'from', 'as', 'global', 'true', 'false'
}

class Lexer:
    def __init__(self, source):
        self.source = source
        self.pos = 0
        self.line = 1
        self.col = 1
        self.tokens = []
        self.indent_stack = [0]

    def error(self, msg):
        raise SyntaxError(f"Лексер (строка {self.line}): {msg}")

    def peek(self, offset=0):
        idx = self.pos + offset
        if idx < len(self.source):
            return self.source[idx]
        return '\0'

    def advance(self):
        ch = self.source[self.pos]
        self.pos += 1
        if ch == '\n':
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def tokenize(self):
        while self.pos < len(self.source):
            # Пропускаем пустые строки и комментарии для обработки отступов
            if self.peek() == '\n':
                self.advance()
                self._handle_newline()
                continue
            if self.peek() == '#':
                while self.peek() not in ('\n', '\0'):
                    self.advance()
                continue
            # Обрабатываем отступы в начале строки
            if self.col == 1:
                self._handle_indent()
            ch = self.peek()
            if ch == '\n':
                self.advance()
                self._handle_newline()
                continue
            if ch == '#':
                while self.peek() not in ('\n', '\0'):
                    self.advance()
                continue
            if ch in ' \t\r':
                self.advance()
                continue
            if ch == '"':
                self._read_string('"')
                continue
            if ch == "'":
                self._read_string("'")
                continue
            if ch.isdigit() or (ch == '.' and self.peek(1).isdigit()):
                self._read_number()
                continue
            if ch.isalpha() or ch == '_':
                self._read_identifier()
                continue
            self._read_operator()
        self.tokens.append(Token('EOF', None, self.line, self.col))
        return self.tokens

    def _handle_newline(self):
        if self.tokens and self.tokens[-1].type == 'NEWLINE':
            return
        self.tokens.append(Token('NEWLINE', '\\n', self.line, self.col))

    def _handle_indent(self):
        indent = 0
        while self.peek() in (' ', '\t'):
            if self.peek() == ' ':
                indent += 1
            else:
                indent += 4
            self.advance()
        if self.peek() in ('\n', '#', '\0'):
            return
        if indent > self.indent_stack[-1]:
            self.indent_stack.append(indent)
            self.tokens.append(Token('INDENT', indent, self.line, self.col))
        else:
            while indent < self.indent_stack[-1]:
                self.indent_stack.pop()
                self.tokens.append(Token('DEDENT', None, self.line, self.col))
            if indent != self.indent_stack[-1]:
                self.error("Несовместимый отступ")

    def _read_string(self, quote):
        self.advance()  # пропускаем открывающую кавычку
        val = []
        while self.peek() != quote and self.peek() != '\0':
            if self.peek() == '\\':
                self.advance()
                esc = self.advance()
                escapes = {'n': '\n', 't': '\t', 'r': '\r', '\\': '\\',
                           '"': '"', "'": "'", '0': '\0'}
                val.append(escapes.get(esc, esc))
            else:
                val.append(self.advance())
        if self.peek() == '\0':
            self.error("Незакрытая строка")
        self.advance()  # пропускаем закрывающую кавычку
        self.tokens.append(Token('STRING', ''.join(val), self.line, self.col))

    def _read_number(self):
        val = []
        is_float = False
        while self.peek().isdigit() or self.peek() == '.':
            if self.peek() == '.':
                if is_float:
                    break
                is_float = True
            val.append(self.advance())
        if is_float:
            self.tokens.append(Token('FLOAT', float(''.join(val)), self.line, self.col))
        else:
            self.tokens.append(Token('INT', int(''.join(val)), self.line, self.col))

    def _read_identifier(self):
        val = []
        while self.peek().isalnum() or self.peek() == '_':
            val.append(self.advance())
        word = ''.join(val)
        if word in KEYWORDS:
            if word == 'true':
                self.tokens.append(Token('TRUE', word, self.line, self.col))
            elif word == 'false':
                self.tokens.append(Token('FALSE', word, self.line, self.col))
            else:
                self.tokens.append(Token(word.upper(), word, self.line, self.col))
        else:
            self.tokens.append(Token('NAME', word, self.line, self.col))

    def _read_operator(self):
        three = self.source[self.pos:self.pos+3]
        two = self.source[self.pos:self.pos+2]
        one = self.peek()
        three_char = {'**=', '//='}
        two_char = {'==', '!=', '<=', '>=', '+=', '-=', '*=', '/=', '//', '**', '->'}
        one_char = {'+', '-', '*', '/', '%', '=', '<', '>', '(', ')', '[', ']',
                     '{', '}', ',', '.', ':', ';'}
        if three in three_char:
            self.advance(); self.advance(); self.advance()
            self.tokens.append(Token('OP', three, self.line, self.col))
        elif two in two_char:
            self.advance(); self.advance()
            if two == '->':
                self.tokens.append(Token('ARROW', two, self.line, self.col))
            else:
                self.tokens.append(Token('OP', two, self.line, self.col))
        elif one in one_char:
            self.advance()
            self.tokens.append(Token('OP', one, self.line, self.col))
        else:
            self.error(f"Неизвестный символ: {one!r}")


# ============================================================
# ПАРСЕР (AST)
# ============================================================

class Node: pass

class NumNode(Node):
    def __init__(self, value): self.value = value
class StrNode(Node):
    def __init__(self, value): self.value = value
class BoolNode(Node):
    def __init__(self, value): self.value = value
class NoneNode(Node):
    pass
class NameNode(Node):
    def __init__(self, name): self.name = name
class ListNode(Node):
    def __init__(self, elements): self.elements = elements
class DictNode(Node):
    def __init__(self, pairs): self.pairs = pairs
class BinOpNode(Node):
    def __init__(self, op, left, right): self.op, self.left, self.right = op, left, right
class UnaryOpNode(Node):
    def __init__(self, op, operand): self.op, self.operand = op, operand
class BoolOpNode(Node):
    def __init__(self, op, left, right): self.op, self.left, self.right = op, left, right
class NotNode(Node):
    def __init__(self, operand): self.operand = operand
class CompareNode(Node):
    def __init__(self, op, left, right): self.op, self.left, self.right = op, left, right
class AssignNode(Node):
    def __init__(self, target, value): self.target, self.value = target, value
class AugAssignNode(Node):
    def __init__(self, op, target, value): self.op, self.target, self.value = op, target, value
class CallNode(Node):
    def __init__(self, func, args, kwargs=None): self.func, self.args = func, args; self.kwargs = kwargs or []
class KwArgNode(Node):
    def __init__(self, name, value): self.name, self.value = name, value
class IndexNode(Node):
    def __init__(self, obj, index): self.obj, self.index = obj, index
class AttrNode(Node):
    def __init__(self, obj, attr): self.obj, self.attr = obj, attr
class IfNode(Node):
    def __init__(self, branches, else_body): self.branches, self.else_body = branches, else_body
class WhileNode(Node):
    def __init__(self, cond, body): self.cond, self.body = cond, body
class ForNode(Node):
    def __init__(self, var, iterable, body): self.var, self.iterable, self.body = var, iterable, body
class FuncDefNode(Node):
    def __init__(self, name, params, body, defaults): self.name, self.params, self.body, self.defaults = name, params, body, defaults
class ReturnNode(Node):
    def __init__(self, value): self.value = value
class BreakNode(Node): pass
class ContinueNode(Node): pass
class PassNode(Node): pass
class ImportNode(Node):
    def __init__(self, module, alias): self.module, self.alias = module, alias
class FromImportNode(Node):
    def __init__(self, module, names): self.module, self.names = module, names
class GlobalNode(Node):
    def __init__(self, names): self.names = names
class ExprStmtNode(Node):
    def __init__(self, expr): self.expr = expr

class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def error(self, msg):
        tok = self.peek()
        raise SyntaxError(f"Парсер (строка {tok.line}): {msg} (получено: {tok.type} {tok.value!r})")

    def peek(self, offset=0):
        idx = self.pos + offset
        if idx < len(self.tokens):
            return self.tokens[idx]
        return self.tokens[-1]

    def advance(self):
        tok = self.tokens[self.pos]
        if self.pos < len(self.tokens) - 1:
            self.pos += 1
        return tok

    def expect(self, type, value=None):
        tok = self.peek()
        if tok.type != type or (value is not None and tok.value != value):
            self.error(f"Ожидалось {type} {value if value else ''}")
        return self.advance()

    def skip_newlines(self):
        while self.peek().type == 'NEWLINE':
            self.advance()
    def skip_colon(self):
        if self.peek().type == 'OP' and self.peek().value == ':':
            self.advance()


    def parse(self):
        body = []
        self.skip_newlines()
        while self.peek().type != 'EOF':
            stmt = self.parse_statement()
            if stmt is not None:
                body.append(stmt)
            self.skip_newlines()
        return body

    def parse_block(self):
        self.expect('INDENT')
        body = []
        self.skip_newlines()
        while self.peek().type not in ('DEDENT', 'EOF'):
            stmt = self.parse_statement()
            if stmt is not None:
                body.append(stmt)
            self.skip_newlines()
        if self.peek().type == 'DEDENT':
            self.advance()
        return body

    def parse_statement(self):
        tok = self.peek()
        if tok.type == 'IF':
            return self.parse_if()
        elif tok.type == 'WHILE':
            return self.parse_while()
        elif tok.type == 'FOR':
            return self.parse_for()
        elif tok.type == 'DEF':
            return self.parse_funcdef()
        elif tok.type == 'RETURN':
            return self.parse_return()
        elif tok.type == 'BREAK':
            self.advance()
            return BreakNode()
        elif tok.type == 'CONTINUE':
            self.advance()
            return ContinueNode()
        elif tok.type == 'PASS':
            self.advance()
            return PassNode()
        elif tok.type == 'IMPORT':
            return self.parse_import()
        elif tok.type == 'FROM':
            return self.parse_from_import()
        elif tok.type == 'GLOBAL':
            return self.parse_global()
        else:
            return self.parse_simple_statement()

    def parse_simple_statement(self):
        expr = self.parse_expr()
        tok = self.peek()
        if tok.type == 'OP' and tok.value in ('=', '+=', '-=', '*=', '/=', '//=', '**='):
            op = self.advance().value
            value = self.parse_expr()
            if op == '=':
                return AssignNode(expr, value)
            else:
                base_op = op[:-1]
                return AugAssignNode(base_op, expr, value)
        return ExprStmtNode(expr)

    def parse_if(self):
        self.expect('IF')
        cond = self.parse_expr()
        self.skip_colon()
        self.skip_newlines()
        self.expect('INDENT')
        body = []
        self.skip_newlines()
        while self.peek().type not in ('DEDENT', 'EOF'):
            stmt = self.parse_statement()
            if stmt is not None:
                body.append(stmt)
            self.skip_newlines()
        if self.peek().type == 'DEDENT':
            self.advance()
        branches = [(cond, body)]
        else_body = None
        while self.peek().type == 'ELIF':
            self.advance()
            elif_cond = self.parse_expr()
            self.skip_colon()
            self.skip_newlines()
            self.expect('INDENT')
            elif_body = []
            self.skip_newlines()
            while self.peek().type not in ('DEDENT', 'EOF'):
                stmt = self.parse_statement()
                if stmt is not None:
                    elif_body.append(stmt)
                self.skip_newlines()
            if self.peek().type == 'DEDENT':
                self.advance()
            branches.append((elif_cond, elif_body))
        if self.peek().type == 'ELSE':
            self.advance()
            self.skip_colon()
            self.skip_newlines()
            self.expect('INDENT')
            else_body = []
            self.skip_newlines()
            while self.peek().type not in ('DEDENT', 'EOF'):
                stmt = self.parse_statement()
                if stmt is not None:
                    else_body.append(stmt)
                self.skip_newlines()
            if self.peek().type == 'DEDENT':
                self.advance()
        return IfNode(branches, else_body)

    def parse_while(self):
        self.expect('WHILE')
        cond = self.parse_expr()
        self.skip_colon()
        self.skip_newlines()
        body = self.parse_block()
        return WhileNode(cond, body)

    def parse_for(self):
        self.expect('FOR')
        var = self.expect('NAME').value
        self.expect('IN')
        iterable = self.parse_expr()
        self.skip_colon()
        self.skip_newlines()
        body = self.parse_block()
        return ForNode(var, iterable, body)

    def parse_funcdef(self):
        self.expect('DEF')
        name = self.expect('NAME').value
        self.expect('OP', '(')
        params = []
        defaults = []
        while self.peek().type != 'OP' or self.peek().value != ')':
            pname = self.expect('NAME').value
            params.append(pname)
            if self.peek().type == 'OP' and self.peek().value == '=':
                self.advance()
                defaults.append(self.parse_expr())
            else:
                defaults.append(None)
            if self.peek().type == 'OP' and self.peek().value == ',':
                self.advance()
        self.expect('OP', ')')
        self.skip_colon()
        self.skip_newlines()
        body = self.parse_block()
        return FuncDefNode(name, params, body, defaults)

    def parse_return(self):
        self.expect('RETURN')
        if self.peek().type in ('NEWLINE', 'EOF', 'DEDENT'):
            return ReturnNode(None)
        return ReturnNode(self.parse_expr())

    def parse_import(self):
        self.expect('IMPORT')
        module = self.expect('NAME').value
        alias = None
        if self.peek().type == 'AS':
            self.advance()
            alias = self.expect('NAME').value
        return ImportNode(module, alias)

    def parse_from_import(self):
        self.expect('FROM')
        module = self.expect('NAME').value
        self.expect('IMPORT')
        names = [self.expect('NAME').value]
        while self.peek().type == 'OP' and self.peek().value == ',':
            self.advance()
            names.append(self.expect('NAME').value)
        return FromImportNode(module, names)

    def parse_global(self):
        self.expect('GLOBAL')
        names = [self.expect('NAME').value]
        while self.peek().type == 'OP' and self.peek().value == ',':
            self.advance()
            names.append(self.expect('NAME').value)
        return GlobalNode(names)

    # --- Выражения ---
    def parse_expr(self):
        return self.parse_or()

    def parse_or(self):
        left = self.parse_and()
        while self.peek().type == 'OR':
            self.advance()
            right = self.parse_and()
            left = BoolOpNode('or', left, right)
        return left

    def parse_and(self):
        left = self.parse_not()
        while self.peek().type == 'AND':
            self.advance()
            right = self.parse_not()
            left = BoolOpNode('and', left, right)
        return left

    def parse_not(self):
        if self.peek().type == 'NOT':
            self.advance()
            return NotNode(self.parse_not())
        return self.parse_comparison()

    def parse_comparison(self):
        left = self.parse_arith()
        while self.peek().type == 'OP' and self.peek().value in ('==', '!=', '<', '>', '<=', '>='):
            op = self.advance().value
            right = self.parse_arith()
            left = CompareNode(op, left, right)
        return left

    def parse_arith(self):
        left = self.parse_term()
        while self.peek().type == 'OP' and self.peek().value in ('+', '-'):
            op = self.advance().value
            right = self.parse_term()
            left = BinOpNode(op, left, right)
        return left

    def parse_term(self):
        left = self.parse_power()
        while self.peek().type == 'OP' and self.peek().value in ('*', '/', '%', '//'):
            op = self.advance().value
            right = self.parse_power()
            left = BinOpNode(op, left, right)
        return left

    def parse_power(self):
        left = self.parse_unary()
        if self.peek().type == 'OP' and self.peek().value == '**':
            self.advance()
            right = self.parse_power()
            return BinOpNode('**', left, right)
        return left

    def parse_unary(self):
        if self.peek().type == 'OP' and self.peek().value == '-':
            self.advance()
            return UnaryOpNode('-', self.parse_unary())
        if self.peek().type == 'OP' and self.peek().value == '+':
            self.advance()
            return self.parse_unary()
        return self.parse_postfix()

    def parse_postfix(self):
        node = self.parse_primary()
        while True:
            tok = self.peek()
            if tok.type == 'OP' and tok.value == '(':
                self.advance()
                args = []
                kwargs = []
                while self.peek().type != 'OP' or self.peek().value != ')':
                    # Проверяем keyword argument: name=value
                    if (self.peek().type == 'NAME' and
                        self.peek(1).type == 'OP' and self.peek(1).value == '='):
                        kw_name = self.advance().value
                        self.advance()  # skip =
                        kw_val = self.parse_expr()
                        kwargs.append(KwArgNode(kw_name, kw_val))
                    else:
                        args.append(self.parse_expr())
                    if self.peek().type == 'OP' and self.peek().value == ',':
                        self.advance()
                self.expect('OP', ')')
                node = CallNode(node, args, kwargs)
            elif tok.type == 'OP' and tok.value == '[':
                self.advance()
                index = self.parse_expr()
                self.expect('OP', ']')
                node = IndexNode(node, index)
            elif tok.type == 'OP' and tok.value == '.':
                self.advance()
                attr = self.expect('NAME').value
                node = AttrNode(node, attr)
            else:
                break
        return node

    def parse_primary(self):
        tok = self.peek()
        if tok.type == 'INT':
            self.advance()
            return NumNode(tok.value)
        elif tok.type == 'FLOAT':
            self.advance()
            return NumNode(tok.value)
        elif tok.type == 'STRING':
            self.advance()
            return StrNode(tok.value)
        elif tok.type == 'TRUE':
            self.advance()
            return BoolNode(True)
        elif tok.type == 'FALSE':
            self.advance()
            return BoolNode(False)
        elif tok.type == 'NONE':
            self.advance()
            return NoneNode()
        elif tok.type == 'NAME':
            self.advance()
            return NameNode(tok.value)
        elif tok.type == 'OP' and tok.value == '(':
            self.advance()
            expr = self.parse_expr()
            self.expect('OP', ')')
            return expr
        elif tok.type == 'OP' and tok.value == '[':
            self.advance()
            elements = []
            while self.peek().type != 'OP' or self.peek().value != ']':
                elements.append(self.parse_expr())
                if self.peek().type == 'OP' and self.peek().value == ',':
                    self.advance()
            self.expect('OP', ']')
            return ListNode(elements)
        elif tok.type == 'OP' and tok.value == '{':
            self.advance()
            pairs = []
            while self.peek().type != 'OP' or self.peek().value != '}':
                key = self.parse_expr()
                self.expect('OP', ':')
                val = self.parse_expr()
                pairs.append((key, val))
                if self.peek().type == 'OP' and self.peek().value == ',':
                    self.advance()
            self.expect('OP', '}')
            return DictNode(pairs)
        else:
            self.error("Неожиданный токен в выражении")


# ============================================================
# ИНТЕРПРЕТАТОР
# ============================================================

class BreakException(Exception): pass
class ContinueException(Exception): pass
class ReturnException(Exception):
    def __init__(self, value): self.value = value

class DebuFunction:
    def __init__(self, name, params, body, closure, interpreter, defaults=None):
        self.name = name
        self.params = params
        self.body = body
        self.closure = closure
        self.interpreter = interpreter
        self.defaults = defaults or []
    def __call__(self, *args, **kwargs):
        local_scope = dict(self.closure)
        for i, param in enumerate(self.params):
            if i < len(args):
                local_scope[param] = args[i]
            elif param in kwargs:
                local_scope[param] = kwargs[param]
            elif i < len(self.defaults) and self.defaults[i] is not None:
                local_scope[param] = self.interpreter.eval(self.defaults[i], self.closure)
            else:
                local_scope[param] = None
        try:
            self.interpreter.exec_block(self.body, local_scope)
        except ReturnException as e:
            return e.value
        return None

class Interpreter:
    def __init__(self):
        self.global_scope = {}
        self.setup_builtins()
        self.module_cache = {}

    def setup_builtins(self):
        self.global_scope.update({
            'print': print,
            'len': len,
            'range': range,
            'str': str,
            'int': int,
            'float': float,
            'bool': bool,
            'list': list,
            'dict': dict,
            'abs': abs,
            'min': min,
            'max': max,
            'sum': sum,
            'sorted': sorted,
            'reversed': reversed,
            'enumerate': enumerate,
            'zip': zip,
            'map': map,
            'filter': filter,
            'type': type,
            'isinstance': isinstance,
            'round': round,
            'repr': repr,
            'format': format,
            'chr': chr,
            'ord': ord,
            'hex': hex,
            'bin': bin,
            'oct': oct,
            'tuple': tuple,
            'set': set,
            'any': any,
            'all': all,
            'open': open,
            'input': input,
        })

    def get_builtin_module(self, name):
        """Возвращает встроенный модуль DebuCode"""
        if name == 'random':
            mod = types.ModuleType('random')
            mod.randint = random.randint
            mod.choice = random.choice
            mod.shuffle = random.shuffle
            mod.random = random.random
            mod.uniform = random.uniform
            mod.randrange = random.randrange
            mod.seed = random.seed
            mod.sample = random.sample
            return mod
        elif name == 'os':
            mod = types.ModuleType('os')
            mod.getcwd = os.getcwd
            mod.chdir = os.chdir
            mod.listdir = os.listdir
            mod.mkdir = os.mkdir
            mod.makedirs = os.makedirs
            mod.remove = os.remove
            mod.rmdir = os.rmdir
            mod.rename = os.rename
            mod.path = os.path
            mod.environ = os.environ
            mod.system = os.system
            mod.name = os.name
            mod.sep = os.sep
            mod.getpid = os.getpid
            mod.exit = os._exit
            return mod
        elif name == 'sys':
            mod = types.ModuleType('sys')
            mod.argv = sys.argv
            mod.exit = sys.exit
            mod.stdout = sys.stdout
            mod.stderr = sys.stderr
            mod.stdin = sys.stdin
            mod.path = sys.path
            mod.version = sys.version
            mod.platform = sys.platform
            mod.maxsize = sys.maxsize
            return mod
        elif name == 'subprocess':
            mod = types.ModuleType('subprocess')
            mod.run = subprocess.run
            mod.Popen = subprocess.Popen
            mod.call = subprocess.call
            mod.check_call = subprocess.check_call
            mod.check_output = subprocess.check_output
            mod.PIPE = subprocess.PIPE
            mod.STDOUT = subprocess.STDOUT
            mod.DEVNULL = subprocess.DEVNULL
            return mod
        elif name == 'tkinter':
            if not HAS_TKINTER:
                raise ImportError("tkinter не установлен в системе")
            return _tkinter_mod
        elif name == 'flask':
            if not HAS_FLASK:
                raise ImportError("Flask не установлен. Установите: pip install flask")
            mod = types.ModuleType('flask')
            mod.Flask = _FlaskClass
            mod.request = _flask_request
            mod.jsonify = _flask_jsonify
            mod.redirect = _flask_redirect
            mod.render_template_string = _flask_render_template_string
            return mod
        elif name == 'math':
            mod = types.ModuleType('math')
            mod.pi = math.pi
            mod.e = math.e
            mod.sqrt = math.sqrt
            mod.sin = math.sin
            mod.cos = math.cos
            mod.tan = math.tan
            mod.log = math.log
            mod.log10 = math.log10
            mod.floor = math.floor
            mod.ceil = math.ceil
            mod.pow = math.pow
            mod.fabs = math.fabs
            mod.factorial = math.factorial
            return mod
        elif name == 'time':
            mod = types.ModuleType('time')
            mod.time = time.time
            mod.sleep = time.sleep
            mod.ctime = time.ctime
            mod.localtime = time.localtime
            mod.strftime = time.strftime
            return mod
        elif name == 'json':
            mod = types.ModuleType('json')
            mod.dumps = json.dumps
            mod.loads = json.loads
            mod.load = json.load
            mod.dump = json.dump
            return mod
        return None

    def load_zip_module(self, name, search_path='.'):
        """Загружает внешний ZIP-пакет DebuCode"""
        zip_path = os.path.join(search_path, name + '.zip')
        if not os.path.exists(zip_path):
            return None
        zf = zipfile.ZipFile(zip_path, 'r')
        # Читаем init.dcm
        init_data = zf.read('init.dcm').decode('utf-8')
        # Парсим init.dcm
        start_file = None
        other_files = []
        for line in init_data.strip().split('\n'):
            line = line.strip()
            if line.startswith('start:'):
                start_file = line.split(':', 1)[1].strip()
            elif line.startswith('files:'):
                files_str = line.split(':', 1)[1].strip()
                other_files = [f.strip() for f in files_str.split('/') if f.strip()]
        # Сначала выполняем вспомогательные файлы, потом стартовый
        file_order = other_files + [start_file]
        # Убираем дубликаты, сохраняя порядок
        seen = set()
        unique_files = []
        for f in file_order:
            if f and f not in seen:
                seen.add(f)
                unique_files.append(f)
        # Общая область видимости пакета
        mod_scope = dict(self.global_scope)
        # Выполняем каждый файл, регистрируем как модуль
        for fname in unique_files:
            source = zf.read(fname).decode('utf-8')
            # Регистрируем файл как модуль до выполнения, чтобы
            # другие файлы могли его импортировать через from ... import
            file_mod = types.ModuleType(fname.replace('.dcm', ''))
            file_scope = dict(mod_scope)
            self.run_source(source, file_scope)
            # Копируем имена в файл-модуль
            for key, val in file_scope.items():
                if not key.startswith('__'):
                    setattr(file_mod, key, val)
                    mod_scope[key] = val  # делаем видимым в других файлах пакета
            # Регистрируем в кеше: имя файла без расширения
            file_base = fname.replace('.dcm', '')
            self.module_cache[file_base] = file_mod
        # Создаём итоговый модуль пакета
        mod = types.ModuleType(name)
        for key, val in mod_scope.items():
            if not key.startswith('__'):
                setattr(mod, key, val)
        zf.close()
        return mod

    def run_source(self, source, scope=None):
        if scope is None:
            scope = self.global_scope
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        self.exec_block(ast, scope)
        return scope

    def exec_block(self, statements, scope):
        for stmt in statements:
            self.exec_stmt(stmt, scope)

    def exec_stmt(self, node, scope):
        if isinstance(node, ExprStmtNode):
            self.eval(node.expr, scope)
        elif isinstance(node, AssignNode):
            value = self.eval(node.value, scope)
            self.assign(node.target, value, scope)
        elif isinstance(node, AugAssignNode):
            current = self.eval(node.target, scope)
            val = self.eval(node.value, scope)
            op = node.op
            if op == '+': result = current + val
            elif op == '-': result = current - val
            elif op == '*': result = current * val
            elif op == '/': result = current / val
            elif op == '//': result = current // val
            elif op == '**': result = current ** val
            else: raise RuntimeError(f"Неизвестный оператор: {op}")
            self.assign(node.target, result, scope)
        elif isinstance(node, IfNode):
            for cond, body in node.branches:
                if self.eval(cond, scope):
                    self.exec_block(body, scope)
                    return
            if node.else_body is not None:
                self.exec_block(node.else_body, scope)
        elif isinstance(node, WhileNode):
            while self.eval(node.cond, scope):
                try:
                    self.exec_block(node.body, scope)
                except BreakException:
                    break
                except ContinueException:
                    continue
        elif isinstance(node, ForNode):
            iterable = self.eval(node.iterable, scope)
            for item in iterable:
                scope[node.var] = item
                try:
                    self.exec_block(node.body, scope)
                except BreakException:
                    break
                except ContinueException:
                    continue
        elif isinstance(node, FuncDefNode):
            func = DebuFunction(node.name, node.params, node.body, dict(scope), self, node.defaults)
            scope[node.name] = func
        elif isinstance(node, ReturnNode):
            value = self.eval(node.value, scope) if node.value else None
            raise ReturnException(value)
        elif isinstance(node, BreakNode):
            raise BreakException()
        elif isinstance(node, ContinueNode):
            raise ContinueException()
        elif isinstance(node, PassNode):
            pass
        elif isinstance(node, ImportNode):
            mod = self.resolve_module(node.module)
            if mod is None:
                raise ImportError(f"Модуль '{node.module}' не найден")
            alias = node.alias if node.alias else node.module
            scope[alias] = mod
        elif isinstance(node, FromImportNode):
            mod = self.resolve_module(node.module)
            if mod is None:
                raise ImportError(f"Модуль '{node.module}' не найден")
            for name in node.names:
                if hasattr(mod, name):
                    scope[name] = getattr(mod, name)
                else:
                    raise ImportError(f"Модуль '{node.module}' не имеет атрибута '{name}'")
        elif isinstance(node, GlobalNode):
            pass  # Упрощённо: всё и так в global_scope
        else:
            raise RuntimeError(f"Неизвестный оператор: {type(node).__name__}")

    def resolve_module(self, name):
        if name in self.module_cache:
            return self.module_cache[name]
        # Сначала пробуем встроенный
        mod = self.get_builtin_module(name)
        if mod is not None:
            self.module_cache[name] = mod
            return mod
        # Потом ZIP-пакет
        mod = self.load_zip_module(name)
        if mod is not None:
            self.module_cache[name] = mod
            return mod
        return None

    def assign(self, target, value, scope):
        if isinstance(target, NameNode):
            scope[target.name] = value
        elif isinstance(target, IndexNode):
            obj = self.eval(target.obj, scope)
            idx = self.eval(target.index, scope)
            obj[idx] = value
        elif isinstance(target, AttrNode):
            obj = self.eval(target.obj, scope)
            setattr(obj, target.attr, value)
        else:
            raise RuntimeError("Неподдерживаемая цель присваивания")

    def eval(self, node, scope):
        if isinstance(node, NumNode):
            return node.value
        elif isinstance(node, StrNode):
            return node.value
        elif isinstance(node, BoolNode):
            return node.value
        elif isinstance(node, NoneNode):
            return None
        elif isinstance(node, NameNode):
            if node.name in scope:
                return scope[node.name]
            if node.name in self.global_scope:
                return self.global_scope[node.name]
            raise NameError(f"Имя '{node.name}' не определено")
        elif isinstance(node, ListNode):
            return [self.eval(e, scope) for e in node.elements]
        elif isinstance(node, DictNode):
            d = {}
            for k, v in node.pairs:
                d[self.eval(k, scope)] = self.eval(v, scope)
            return d
        elif isinstance(node, BinOpNode):
            left = self.eval(node.left, scope)
            right = self.eval(node.right, scope)
            return self.binop(node.op, left, right)
        elif isinstance(node, UnaryOpNode):
            val = self.eval(node.operand, scope)
            if node.op == '-':
                return -val
            return val
        elif isinstance(node, BoolOpNode):
            left = self.eval(node.left, scope)
            if node.op == 'and':
                if not left:
                    return left
                return self.eval(node.right, scope)
            else:  # or
                if left:
                    return left
                return self.eval(node.right, scope)
        elif isinstance(node, NotNode):
            return not self.eval(node.operand, scope)
        elif isinstance(node, CompareNode):
            left = self.eval(node.left, scope)
            right = self.eval(node.right, scope)
            op = node.op
            if op == '==': return left == right
            elif op == '!=': return left != right
            elif op == '<': return left < right
            elif op == '>': return left > right
            elif op == '<=': return left <= right
            elif op == '>=': return left >= right
        elif isinstance(node, CallNode):
            func = self.eval(node.func, scope)
            args = [self.eval(a, scope) for a in node.args]
            kwargs = {}
            for kw in node.kwargs:
                kwargs[kw.name] = self.eval(kw.value, scope)
            return func(*args, **kwargs)
        elif isinstance(node, IndexNode):
            obj = self.eval(node.obj, scope)
            idx = self.eval(node.index, scope)
            return obj[idx]
        elif isinstance(node, AttrNode):
            obj = self.eval(node.obj, scope)
            return getattr(obj, node.attr)
        else:
            raise RuntimeError(f"Неизвестное выражение: {type(node).__name__}")

    def binop(self, op, left, right):
        if op == '+':
            return left + right
        elif op == '-':
            return left - right
        elif op == '*':
            return left * right
        elif op == '/':
            return left / right
        elif op == '%':
            return left % right
        elif op == '//':
            return left // right
        elif op == '**':
            return left ** right
        else:
            raise RuntimeError(f"Неизвестный бинарный оператор: {op}")


# ============================================================
# ЗАПУСК
# ============================================================

def run_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        source = f.read()
    interp = Interpreter()
    # Передаём путь к скрипту для поиска ZIP-пакетов
    script_dir = os.path.dirname(os.path.abspath(filepath))
    interp.module_cache = {}
    # Патчим load_zip_module для поиска в директории скрипта
    orig_load = interp.load_zip_module
    def patched_load(name, search_path=None):
        if search_path is None:
            search_path = script_dir
        return orig_load(name, search_path)
    interp.load_zip_module = patched_load
    try:
        interp.run_source(source)
    except Exception as e:
        print(f"Ошибка DebuCode: {e}", file=sys.stderr)
        traceback.print_exc()

def main():
    if len(sys.argv) < 2:
        print("DebuCode Minimal v0.2")
        print("Использование: python debucode.py <файл.dcm>")
        print()
        print("Встроенные модули: random, os, sys, subprocess, tkinter, flask,")
        print("                    math, time, json")
        print()
        print("Внешние модули: ZIP-архивы с init.dcm внутри")
        sys.exit(1)
    filepath = sys.argv[1]
    if not os.path.exists(filepath):
        print(f"Файл не найден: {filepath}", file=sys.stderr)
        sys.exit(1)
    run_file(filepath)

if __name__ == '__main__':
    main()
