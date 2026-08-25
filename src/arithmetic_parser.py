# arithmetic_parser.py
# Step 1: Grammar -> AST for four arithmetic operations (+ - * /) + function calls

import re
from dataclasses import dataclass, field
from typing import Any, List

TOKEN_SPEC = [
    ('NUMBER',    r'\d+(\.\d*)?'),
    ('FUNC_NAME', r'[a-z][a-zA-Z0-9_]*'),   # function name (letter-first identifier)
    ('PLUS',      r'\+'),
    ('MINUS',     r'-'),
    ('MUL',       r'\*'),
    ('DIV',       r'/'),
    ('LPAREN',    r'\('),
    ('RPAREN',    r'\)'),
    ('COMMA',     r','),
    ('SKIP',      r'[ \t]+'),
]
TOKEN_RE = re.compile('|'.join(f'(?P<{n}>{p})' for n, p in TOKEN_SPEC))


@dataclass
class Token:
    kind: str
    value: str


def tokenize(text: str) -> list:
    tokens = []
    pos = 0
    for m in TOKEN_RE.finditer(text):
        if m.start() != pos:
            unmatched = text[pos:m.start()]
            raise SyntaxError(f"Unexpected character(s): {unmatched!r} at position {pos}")
        pos = m.end()
        kind = m.lastgroup
        if kind == 'SKIP':
            continue
        tokens.append(Token(kind, m.group()))
    if pos != len(text):
        unmatched = text[pos:]
        raise SyntaxError(f"Unexpected character(s): {unmatched!r} at position {pos}")
    tokens.append(Token('EOF', ''))
    return tokens


# AST Nodes
@dataclass
class Num:
    value: float


@dataclass
class BinOp:
    op: str
    left: Any
    right: Any


@dataclass
class FuncCall:
    name: str
    args: List[Any] = field(default_factory=list)


# Parser (Recursive Descent)
# Grammar:
#   Expr     -> Term   (('+' | '-') Term)*
#   Term     -> Factor (('*' | '/') Factor)*
#   Factor   -> FuncCall | '(' Expr ')' | NUMBER
#   FuncCall -> FUNC_NAME '(' ArgList? ')'
#   ArgList  -> Expr (',' Expr)*

class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self):
        return self.tokens[self.pos]

    def consume(self, kind):
        tok = self.tokens[self.pos]
        assert tok.kind == kind, f"Expected {kind}, got {tok.kind}"
        self.pos += 1
        return tok

    def parse(self):
        node = self.expr()
        self.consume('EOF')
        return node

    def expr(self):
        node = self.term()
        while self.peek().kind in ('PLUS', 'MINUS'):
            op = self.tokens[self.pos].value
            self.pos += 1
            node = BinOp(op, node, self.term())
        return node

    def term(self):
        node = self.factor()
        while self.peek().kind in ('MUL', 'DIV'):
            op = self.tokens[self.pos].value
            self.pos += 1
            node = BinOp(op, node, self.factor())
        return node

    def factor(self):
        tok = self.peek()
        if tok.kind == 'FUNC_NAME':
            return self.func_call()
        if tok.kind == 'NUMBER':
            self.pos += 1
            return Num(float(tok.value))
        elif tok.kind == 'LPAREN':
            self.consume('LPAREN')
            node = self.expr()
            self.consume('RPAREN')
            return node
        raise SyntaxError(f"Unexpected token: {tok}")

    def func_call(self):
        name_tok = self.consume('FUNC_NAME')
        self.consume('LPAREN')
        args = []
        if self.peek().kind != 'RPAREN':
            args.append(self.expr())
            while self.peek().kind == 'COMMA':
                self.consume('COMMA')
                args.append(self.expr())
        self.consume('RPAREN')
        return FuncCall(name_tok.value, args)


if __name__ == '__main__':
    import pprint
    for expr in [
        "(3 + 5) * 2 - 8 / 4",
        "sin(30)",
        "max(3 + 1, 2 * 5)",
        "pow(2, 10) + 1",
    ]:
        tokens = tokenize(expr)
        ast = Parser(tokens).parse()
        print("Expression:", expr)
        print("AST:")
        pprint.pprint(ast)
        print()
