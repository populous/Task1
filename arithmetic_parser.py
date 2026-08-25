# arithmetic_parser.py
# Step 1: Grammar -> AST for four arithmetic operations (+ - * /)

import re
from dataclasses import dataclass
from typing import Any

TOKEN_SPEC = [
    ('NUMBER', r'\d+(\.\d*)?'),
    ('PLUS',   r'\+'),
    ('MINUS',  r'-'),
    ('MUL',    r'\*'),
    ('DIV',    r'/'),
    ('LPAREN', r'\('),
    ('RPAREN', r'\)'),
    ('SKIP',   r'[ \t]+'),
]
TOKEN_RE = re.compile('|'.join(f'(?P<{n}>{p})' for n, p in TOKEN_SPEC))


@dataclass
class Token:
    kind: str
    value: str


def tokenize(text: str) -> list:
    tokens = []
    for m in TOKEN_RE.finditer(text):
        kind = m.lastgroup
        if kind == 'SKIP':
            continue
        tokens.append(Token(kind, m.group()))
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


# Parser (Recursive Descent)
# Grammar:
#   Expr   -> Term   (('+' | '-') Term)*
#   Term   -> Factor (('*' | '/') Factor)*
#   Factor -> '(' Expr ')' | NUMBER

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
        if tok.kind == 'NUMBER':
            self.pos += 1
            return Num(float(tok.value))
        elif tok.kind == 'LPAREN':
            self.consume('LPAREN')
            node = self.expr()
            self.consume('RPAREN')
            return node
        raise SyntaxError(f"Unexpected token: {tok}")


if __name__ == '__main__':
    import pprint
    expr = "(3 + 5) * 2 - 8 / 4"
    tokens = tokenize(expr)
    ast = Parser(tokens).parse()
    print("Expression:", expr)
    print("AST:")
    pprint.pprint(ast)
