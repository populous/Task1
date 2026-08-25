# antlr_parser_bridge.py
# Step 1 (ANTLR 버전): Arithmetic.g4 로부터 생성된 파서를 사용하여
# 4칙연산 수식을 AST(BinOp/Num)로 변환한다.
#
# ── 사전 준비 ──────────────────────────────────────────────────
# 1) ANTLR4 jar 다운로드:
#      wget https://www.antlr.org/download/antlr-4.13.1-complete.jar
#
# 2) 파서 코드 생성:
#      java -jar antlr-4.13.1-complete.jar -Dlanguage=Python3 -visitor Arithmetic.g4
#    → ArithmeticLexer.py, ArithmeticParser.py, ArithmeticVisitor.py 생성됨
#
# 3) ANTLR4 Python 런타임 설치:
#      pip install antlr4-python3-runtime==4.13.1
# ──────────────────────────────────────────────────────────────

from __future__ import annotations
from dataclasses import dataclass
from typing import Any


# ── AST Nodes (arithmetic_parser.py 와 동일) ───────────────────
@dataclass
class Num:
    value: float

@dataclass
class BinOp:
    op: str
    left: Any
    right: Any


# ── Visitor: Parse Tree → AST ──────────────────────────────────
def build_ast_visitor():
    """
    ANTLR4 생성 파일이 있을 때만 임포트한다.
    생성 파일 없이도 이 모듈 자체는 임포트 가능하도록 lazy import 사용.
    """
    try:
        from antlr4 import CommonTokenStream, InputStream
        from ArithmeticLexer import ArithmeticLexer
        from ArithmeticParser import ArithmeticParser
        from ArithmeticVisitor import ArithmeticVisitor
    except ImportError as e:
        raise ImportError(
            "ANTLR4 생성 파일이 없습니다. README의 사전 준비 단계를 실행하세요.\n"
            f"원인: {e}"
        )

    class ASTBuilder(ArithmeticVisitor):
        """ANTLR parse tree를 BinOp/Num AST로 변환하는 Visitor."""

        def visitProgram(self, ctx):
            return self.visit(ctx.expr())

        def visitExpr(self, ctx):
            # expr : term ( (PLUS | MINUS) term )*
            node = self.visit(ctx.term(0))
            for i in range(1, len(ctx.term())):
                op = ctx.getChild(2 * i - 1).getText()   # operator token
                node = BinOp(op, node, self.visit(ctx.term(i)))
            return node

        def visitTerm(self, ctx):
            # term : factor ( (MUL | DIV) factor )*
            node = self.visit(ctx.factor(0))
            for i in range(1, len(ctx.factor())):
                op = ctx.getChild(2 * i - 1).getText()
                node = BinOp(op, node, self.visit(ctx.factor(i)))
            return node

        def visitParenExpr(self, ctx):
            return self.visit(ctx.expr())

        def visitNumber(self, ctx):
            return Num(float(ctx.NUMBER().getText()))

    return ASTBuilder


def parse_with_antlr(text: str):
    """
    ANTLR4 파서로 수식 문자열을 파싱하여 AST를 반환한다.
    """
    from antlr4 import CommonTokenStream, InputStream
    from ArithmeticLexer import ArithmeticLexer
    from ArithmeticParser import ArithmeticParser

    input_stream = InputStream(text)
    lexer        = ArithmeticLexer(input_stream)
    stream       = CommonTokenStream(lexer)
    parser       = ArithmeticParser(stream)

    tree         = parser.program()           # parse tree 생성
    ASTBuilder   = build_ast_visitor()
    ast          = ASTBuilder().visit(tree)   # AST 변환
    return ast


# ── Fallback: 수동 파서 (ANTLR 없을 때) ────────────────────────
def parse_fallback(text: str):
    """arithmetic_parser.py의 수동 파서를 사용 (ANTLR 없는 환경용)."""
    from arithmetic_parser import tokenize, Parser
    return Parser(tokenize(text)).parse()


def parse(text: str):
    """ANTLR 파서 우선, 없으면 수동 파서로 자동 fallback."""
    try:
        return parse_with_antlr(text)
    except ImportError:
        print("[bridge] ANTLR 런타임 없음 → 수동 파서 사용")
        return parse_fallback(text)


# ── Demo ───────────────────────────────────────────────────────
if __name__ == '__main__':
    import pprint
    expr = "(3 + 5) * 2 - 8 / 4"
    ast  = parse(expr)
    print(f"Expression : {expr}")
    print("AST:")
    pprint.pprint(ast)
