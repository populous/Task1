# pipeline.py
# ============================================================
# 코드 개발의 일반 과정 — 구체 구현 및 파이프라인 조립
#
# pipeline_abc.py 의 추상 기반 클래스를 상속하여
# 이 프로젝트의 모든 단계를 하나의 Pipeline으로 연결한다.
#
# 실행:
#   python pipeline.py
# ============================================================

from __future__ import annotations

from typing import Any, List

from pipeline_abc import (
    BaseLexer,
    BaseParser,
    BaseIRGen,
    BaseAllocator,
    BaseEmitter,
    BasePipeline,
)

# ── 기존 모듈 임포트 ──────────────────────────────────────────
from arithmetic_parser import tokenize as _tokenize, Parser as _Parser
from ir_generator import IRGenerator
from register_allocator import (
    RegisterAllocator,
    apply_allocation,
    PHYSICAL_REGS,
)
from code_emitter import CodeEmitter


# ── Stage 1: Lexer 구체 구현 ──────────────────────────────────
class ArithmeticLexer(BaseLexer):
    """
    [Stage 1 — 어휘 분석]
    정규식 기반 토크나이저로 수식 문자열을 토큰 리스트로 변환한다.
    """

    def tokenize(self, source: str) -> List[Any]:
        return _tokenize(source)


# ── Stage 2: Parser 구체 구현 ─────────────────────────────────
class ArithmeticParser(BaseParser):
    """
    [Stage 2 — 구문 분석]
    재귀 하강 파서로 토큰 리스트를 AST로 변환한다.
    문법: Expr → Term ((+|-) Term)*
          Term → Factor ((*|/) Factor)*
          Factor → FuncCall | '(' Expr ')' | NUMBER
    """

    def parse(self, tokens: List[Any]) -> Any:
        return _Parser(tokens).parse()


# ── Stage 3: IRGen 구체 구현 ──────────────────────────────────
class ArithmeticIRGen(BaseIRGen):
    """
    [Stage 3 — 중간 코드 생성]
    AST를 3-주소 코드(Three-Address Code) IR로 변환한다.
    임시 변수 t1, t2, … 를 사용하여 표현식을 선형화한다.
    """

    def generate(self, ast: Any) -> List[Any]:
        gen = IRGenerator()
        gen.generate(ast)
        return gen.instrs


# ── Stage 4: Allocator 구체 구현 ─────────────────────────────
class ArithmeticAllocator(BaseAllocator):
    """
    [Stage 4 — 자원(레지스터) 할당]
    Linear Scan 알고리즘으로 IR 임시 변수를 물리 레지스터에 배정한다.
    레지스터 부족 시 메모리 스필(MEM[n])을 사용한다.
    """

    def __init__(self, regs: List[str] = None):
        self.regs = regs or list(PHYSICAL_REGS)

    def allocate(self, ir: List[Any]) -> List[str]:
        allocator = RegisterAllocator(self.regs)
        alloc = allocator.allocate(ir)
        return apply_allocation(ir, alloc)


# ── Stage 5: Emitter 구체 구현 ───────────────────────────────
class ArithmeticEmitter(BaseEmitter):
    """
    [Stage 5 — 코드 방출]
    AST를 EVM 스타일 스택 머신 바이트코드로 변환한다.
    PUSH / ADD / SUB / MUL / DIV / CALL 명령어를 방출한다.
    """

    def __init__(self):
        self._emitter = CodeEmitter()

    def emit(self, ast: Any) -> None:
        self._emitter = CodeEmitter()   # 재사용 시 초기화
        self._emitter.emit(ast)

    def dump(self) -> None:
        self._emitter.dump()

    def serialize(self) -> str:
        return self._emitter.to_hex()


# ── Pipeline 구체 구현 ────────────────────────────────────────
class ArithmeticPipeline(BasePipeline):
    """
    [Pipeline — 전체 파이프라인 조합]
    코드 개발의 일반 과정 5단계를 순서대로 실행한다:

      소스 문자열
        → [Lexer]     토큰 스트림
        → [Parser]    AST
        → [IRGen]     Three-Address Code
        → [Allocator] 레지스터 할당된 IR
        → [Emitter]   바이트코드
    """

    def __init__(self, regs: List[str] = None):
        super().__init__(
            lexer     = ArithmeticLexer(),
            parser    = ArithmeticParser(),
            irgen     = ArithmeticIRGen(),
            allocator = ArithmeticAllocator(regs),
            emitter   = ArithmeticEmitter(),
        )

    def describe(self) -> str:
        stages = [
            ("Stage 1", "Lexer",     type(self.lexer).__name__),
            ("Stage 2", "Parser",    type(self.parser).__name__),
            ("Stage 3", "IRGen",     type(self.irgen).__name__),
            ("Stage 4", "Allocator", type(self.allocator).__name__),
            ("Stage 5", "Emitter",   type(self.emitter).__name__),
        ]
        lines = ["ArithmeticPipeline 구성:"]
        for stage_id, role, cls in stages:
            lines.append(f"  [{stage_id}] {role:<12} → {cls}")
        return "\n".join(lines)


# ── Demo ──────────────────────────────────────────────────────
if __name__ == '__main__':
    pipeline = ArithmeticPipeline()

    print("=" * 55)
    print(pipeline.describe())
    print("=" * 55)

    test_cases = [
        "(3 + 5) * 2 - 8 / 4",
        "sin(30)",
        "max(3 + 1, 2 * 5)",
        "pow(2, 10) + 1",
    ]

    for source in test_cases:
        print(f"\n{'─'*55}")
        result = pipeline.run(source)
        result.display()

    print(f"\n{'='*55}")
    print("파이프라인 완료")
