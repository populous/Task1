# pipeline_abc.py
# ============================================================
# 코드 개발의 일반 과정 — 추상 기반 클래스 (Abstract Base Classes)
#
# 컴파일러/파서 파이프라인의 각 단계를 독립적인 추상 계층으로 정의한다.
# 구체 구현은 pipeline.py에서 이 ABC들을 상속·구현한다.
#
# 파이프라인 단계 (일반화):
#   Stage 1: Lexer    — 문자열 → 토큰 스트림
#   Stage 2: Parser   — 토큰 스트림 → AST
#   Stage 3: IRGen    — AST → 중간 표현(IR)
#   Stage 4: Allocator— IR → 자원(레지스터) 할당된 IR
#   Stage 5: Emitter  — 할당된 IR → 최종 출력(바이트코드 등)
# ============================================================

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, List


# ── Stage 1: Lexer ────────────────────────────────────────────
class BaseLexer(ABC):
    """
    [일반화] 어휘 분석기 (Lexical Analyser / Tokenizer)
    소스 문자열을 언어의 최소 의미 단위(토큰)로 분해한다.
    """

    @abstractmethod
    def tokenize(self, source: str) -> List[Any]:
        """
        Args:
            source: 원시 소스 문자열
        Returns:
            토큰 객체의 리스트 (마지막은 EOF 토큰)
        """


# ── Stage 2: Parser ───────────────────────────────────────────
class BaseParser(ABC):
    """
    [일반화] 구문 분석기 (Syntax Analyser / Parser)
    토큰 스트림을 문법 규칙에 따라 AST(추상 구문 트리)로 변환한다.
    """

    @abstractmethod
    def parse(self, tokens: List[Any]) -> Any:
        """
        Args:
            tokens: BaseLexer.tokenize()의 반환값
        Returns:
            AST 루트 노드 (Num | BinOp | FuncCall …)
        """


# ── Stage 3: IRGen ────────────────────────────────────────────
class BaseIRGen(ABC):
    """
    [일반화] 중간 코드 생성기 (Intermediate Representation Generator)
    AST를 플랫폼 독립적인 중간 표현(IR)으로 변환한다.
    Three-Address Code, SSA, CIL 등 다양한 IR을 대상으로 한다.
    """

    @abstractmethod
    def generate(self, ast: Any) -> List[Any]:
        """
        Args:
            ast: BaseParser.parse()의 반환값
        Returns:
            IR 명령어 리스트
        """


# ── Stage 4: Allocator ────────────────────────────────────────
class BaseAllocator(ABC):
    """
    [일반화] 자원 할당기 (Resource / Register Allocator)
    IR의 임시 변수를 물리적 자원(레지스터, 메모리 슬롯 등)에 매핑한다.
    """

    @abstractmethod
    def allocate(self, ir: List[Any]) -> List[str]:
        """
        Args:
            ir: BaseIRGen.generate()의 반환값
        Returns:
            자원이 할당된 IR 명령어 문자열 리스트
        """


# ── Stage 5: Emitter ──────────────────────────────────────────
class BaseEmitter(ABC):
    """
    [일반화] 코드 방출기 (Code Emitter / Backend)
    AST 또는 IR을 타깃 아키텍처의 명령어(바이트코드, 어셈블리 등)로 변환한다.
    """

    @abstractmethod
    def emit(self, ast: Any) -> None:
        """AST를 순회하며 내부 명령어 리스트에 방출한다."""

    @abstractmethod
    def dump(self) -> None:
        """방출된 명령어를 출력한다."""

    @abstractmethod
    def serialize(self) -> str:
        """방출된 명령어를 직렬화된 문자열(hex, text 등)로 반환한다."""


# ── Pipeline (조합자) ─────────────────────────────────────────
class BasePipeline(ABC):
    """
    [일반화] 파이프라인 조합자 (Pipeline Orchestrator)
    위의 5단계를 순서대로 연결하여 소스 문자열에서 최종 출력까지 실행한다.

    코드 개발의 일반 과정:
      명세 → 어휘분석 → 구문분석 → IR생성 → 자원할당 → 코드방출
    """

    def __init__(
        self,
        lexer: BaseLexer,
        parser: BaseParser,
        irgen: BaseIRGen,
        allocator: BaseAllocator,
        emitter: BaseEmitter,
    ):
        self.lexer     = lexer
        self.parser    = parser
        self.irgen     = irgen
        self.allocator = allocator
        self.emitter   = emitter

    def run(self, source: str) -> "PipelineResult":
        """소스 문자열 한 줄을 전체 파이프라인으로 처리한다."""
        tokens        = self.lexer.tokenize(source)
        ast           = self.parser.parse(tokens)
        ir            = self.irgen.generate(ast)
        allocated_ir  = self.allocator.allocate(ir)
        self.emitter.emit(ast)
        bytecode      = self.emitter.serialize()
        return PipelineResult(
            source=source,
            tokens=tokens,
            ast=ast,
            ir=ir,
            allocated_ir=allocated_ir,
            bytecode=bytecode,
        )

    @abstractmethod
    def describe(self) -> str:
        """파이프라인 구성을 사람이 읽을 수 있는 형태로 반환한다."""


# ── 결과 컨테이너 ──────────────────────────────────────────────
class PipelineResult:
    """각 단계의 출력을 하나의 객체로 묶어 반환한다."""

    def __init__(
        self,
        source: str,
        tokens: List[Any],
        ast: Any,
        ir: List[Any],
        allocated_ir: List[str],
        bytecode: str,
    ):
        self.source       = source
        self.tokens       = tokens
        self.ast          = ast
        self.ir           = ir
        self.allocated_ir = allocated_ir
        self.bytecode     = bytecode

    def display(self) -> None:
        """파이프라인 각 단계의 결과를 단계별로 출력한다."""
        print(f"[Stage 1] Source      : {self.source}")
        print(f"[Stage 1] Tokens      : {[t.kind for t in self.tokens]}")
        print(f"[Stage 2] AST         : {self.ast}")
        print(f"[Stage 3] IR          :")
        for instr in self.ir:
            print(f"            {instr}")
        print(f"[Stage 4] Allocated IR:")
        for line in self.allocated_ir:
            print(f"            {line}")
        print(f"[Stage 5] Bytecode    : {self.bytecode}")
