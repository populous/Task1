# constraint/type_guard.py
# ============================================================
# 타입 가드 (Type Guard)
#
# Lowering 파이프라인의 각 단계에서 레지스터 유형 불일치를
# 조기에 탐지(Fail Fast)하여 무한 디버그를 사전 차단한다.
#
# 검증 시점:
#   1. [Syntax Guard]   AST 레벨  — 미등록 연산자·함수, arity 불일치
#   2. [IR Guard]       IR  레벨  — 미정의 임시변수 사용, SSA 위반
#   3. [Alloc Guard]    할당 레벨 — 레지스터 유형 불일치, 뱅크 초과
#
# 사용:
#   from constraint.type_guard import TypeGuard
#   guard = TypeGuard()
#   guard.check_ast(ast)          # AST 검증
#   guard.check_ir(ir_instrs)     # IR 검증
#   guard.check_allocation(alloc) # 할당 결과 검증
# ============================================================

from __future__ import annotations

import sys
import os
from dataclasses import dataclass, field
from typing import Any, List, Optional

# 상위 src/ 를 sys.path에 추가하여 기존 모듈 import 허용
_SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from constraint.register_type_map import RegisterTypeMap


# ── 위반 레코드 ────────────────────────────────────────────────

@dataclass
class Violation:
    stage: str          # 'SYNTAX' | 'IR' | 'ALLOC'
    level: str          # 'ERROR' | 'WARN'
    code: str           # 위반 코드 (예: 'UNREGISTERED_OP')
    message: str        # 사람이 읽을 수 있는 설명
    context: str = ''   # 위반이 발생한 AST 노드 / IR 라인 텍스트

    def __str__(self) -> str:
        ctx = f" | context: {self.context}" if self.context else ''
        return f"[{self.stage}][{self.level}] {self.code}: {self.message}{ctx}"


@dataclass
class GuardReport:
    violations: List[Violation] = field(default_factory=list)

    def add(self, v: Violation) -> None:
        self.violations.append(v)

    @property
    def has_error(self) -> bool:
        return any(v.level == 'ERROR' for v in self.violations)

    @property
    def errors(self) -> List[Violation]:
        return [v for v in self.violations if v.level == 'ERROR']

    @property
    def warnings(self) -> List[Violation]:
        return [v for v in self.violations if v.level == 'WARN']

    def summary(self) -> str:
        lines = [f"총 위반: {len(self.violations)}건 "
                 f"(오류={len(self.errors)}, 경고={len(self.warnings)})"]
        for v in self.violations:
            lines.append(f"  {v}")
        return '\n'.join(lines)

    def raise_if_errors(self) -> None:
        """오류가 있으면 ValueError를 발생시켜 파이프라인을 중단한다."""
        if self.has_error:
            msgs = '\n'.join(str(v) for v in self.errors)
            raise ValueError(f"TypeGuard 오류 — Lowering 중단:\n{msgs}")


# ── TypeGuard 메인 클래스 ──────────────────────────────────────

class TypeGuard:
    """
    Lowering 파이프라인의 각 단계에서 레지스터 유형 제약을 검증한다.
    """

    def __init__(self, contract_path: Optional[str] = None):
        self.rtm = RegisterTypeMap(contract_path)

    # ── [1] Syntax Guard: AST 검증 ────────────────────────────

    def check_ast(self, node: Any, report: Optional[GuardReport] = None) -> GuardReport:
        """
        AST를 재귀 순회하며 다음을 검증한다:
          - BinOp: 연산자가 contract에 등록되어 있는지
          - FuncCall: 함수가 contract에 등록되어 있는지, arity 일치 여부
        """
        if report is None:
            report = GuardReport()
        self._walk_ast(node, report)
        return report

    def _walk_ast(self, node: Any, report: GuardReport) -> None:
        if node is None:
            return

        cls = type(node).__name__

        if cls == 'BinOp':
            sym = node.op
            if not self.rtm.is_registered_op(sym):
                report.add(Violation(
                    stage='SYNTAX', level='ERROR',
                    code='UNREGISTERED_OP',
                    message=f"연산자 '{sym}'이 contract에 등록되지 않음",
                    context=f"BinOp({sym})",
                ))
            self._walk_ast(node.left, report)
            self._walk_ast(node.right, report)

        elif cls == 'FuncCall':
            name = node.name
            if not self.rtm.is_registered_func(name):
                report.add(Violation(
                    stage='SYNTAX', level='ERROR',
                    code='UNREGISTERED_FUNC',
                    message=f"함수 '{name}'이 contract에 등록되지 않음",
                    context=f"FuncCall({name})",
                ))
            else:
                expected = self.rtm.arity_of_func(name)
                actual   = len(node.args)
                if expected >= 0 and actual != expected:
                    report.add(Violation(
                        stage='SYNTAX', level='ERROR',
                        code='ARITY_MISMATCH',
                        message=(f"함수 '{name}' 인자 수 불일치: "
                                 f"contract={expected}, 실제={actual}"),
                        context=f"FuncCall({name}, args={actual})",
                    ))
            for arg in getattr(node, 'args', []):
                self._walk_ast(arg, report)

        elif cls == 'Num':
            pass  # 리터럴은 검증 불필요

        else:
            # 알 수 없는 노드 — 재귀 가능한 속성 탐색
            for attr in ('left', 'right', 'args', 'operand'):
                child = getattr(node, attr, None)
                if isinstance(child, list):
                    for c in child:
                        self._walk_ast(c, report)
                elif child is not None:
                    self._walk_ast(child, report)

    # ── [2] IR Guard: 3-주소 코드 검증 ───────────────────────

    def check_ir(self, instrs: list, report: Optional[GuardReport] = None) -> GuardReport:
        """
        IR 명령어 목록을 검증한다:
          - 임시변수가 사용 전 정의되었는지 (Use-Before-Def)
          - 같은 임시변수가 두 번 이상 정의되는지 (SSA 위반)
        """
        if report is None:
            report = GuardReport()

        defined: set = set()
        defined_count: dict = {}

        for idx, instr in enumerate(instrs):
            line = f"[{idx}] {instr}"

            # Use-Before-Def 검증
            for arg in (instr.arg1, instr.arg2):
                if arg and arg.startswith('t') and arg not in defined:
                    report.add(Violation(
                        stage='IR', level='ERROR',
                        code='USE_BEFORE_DEF',
                        message=f"임시변수 '{arg}' 정의 전 사용",
                        context=line,
                    ))

            # SSA 위반 검증 (단일 정의 원칙)
            res = instr.result
            defined_count[res] = defined_count.get(res, 0) + 1
            if defined_count[res] > 1:
                report.add(Violation(
                    stage='IR', level='WARN',
                    code='SSA_VIOLATION',
                    message=f"임시변수 '{res}'가 {defined_count[res]}번 정의됨 (SSA 위반)",
                    context=line,
                ))
            defined.add(res)

        return report

    # ── [3] Alloc Guard: 레지스터 할당 결과 검증 ─────────────

    def check_allocation(
        self,
        instrs: list,
        alloc: dict,
        report: Optional[GuardReport] = None,
    ) -> GuardReport:
        """
        할당 결과(alloc)를 검증한다:
          - 각 임시변수가 올바른 레지스터 유형 뱅크에 배정됐는지
          - 뱅크 용량 초과 여부 (뱅크별 사용 레지스터 수 집계)
        """
        if report is None:
            report = GuardReport()

        # temp → 기대 reg_type 계산
        expected_type: dict = {}
        for instr in instrs:
            rtype = None
            if instr.op == 'call':
                rtype = self.rtm.reg_type_of_func(instr.arg1)
            elif instr.op:
                rtype = self.rtm.reg_type_of_op(instr.op)
            if rtype and instr.result:
                expected_type[instr.result] = rtype

        # 뱅크별 실제 사용 레지스터 집합
        bank_usage: dict = {k: set() for k in self.rtm.banks}

        for temp, reg in alloc.items():
            if reg.startswith('MEM'):
                continue  # 스필은 유형 검증 제외

            # 어느 뱅크에 속하는지 확인
            actual_type = None
            for btype, bregs in self.rtm.banks.items():
                if reg in bregs:
                    actual_type = btype
                    bank_usage[btype].add(reg)
                    break

            if actual_type is None:
                report.add(Violation(
                    stage='ALLOC', level='ERROR',
                    code='UNKNOWN_REG',
                    message=f"'{reg}'은 어느 뱅크에도 속하지 않는 미정의 레지스터",
                    context=f"{temp} -> {reg}",
                ))
                continue

            exp = expected_type.get(temp)
            if exp and actual_type != exp:
                report.add(Violation(
                    stage='ALLOC', level='ERROR',
                    code='REG_TYPE_MISMATCH',
                    message=(f"임시변수 '{temp}': "
                             f"기대 유형={exp}, 실제 할당 유형={actual_type} ({reg})"),
                    context=f"{temp} -> {reg}",
                ))

        # 뱅크 용량 초과 경고
        for btype, used_regs in bank_usage.items():
            capacity = len(self.rtm.banks[btype])
            if len(used_regs) >= capacity:
                report.add(Violation(
                    stage='ALLOC', level='WARN',
                    code='BANK_FULL',
                    message=(f"{btype} 뱅크 포화 "
                             f"({len(used_regs)}/{capacity}): {sorted(used_regs)}"),
                    context=f"register_bank[{btype}]",
                ))

        return report


# ── 단독 실행 (데모) ───────────────────────────────────────────
if __name__ == '__main__':
    # 간단한 AST 모의 객체로 Syntax Guard 테스트
    from arithmetic_parser import tokenize, Parser
    from ir_generator import IRGenerator
    from register_allocator import RegisterAllocator, apply_allocation

    guard = TypeGuard()

    # --- Syntax Guard ---
    print("=== [1] Syntax Guard: AST 검증 ===")
    for expr in ["(3 + 5) * 2", "max(1, 2)", "sin(30)", "pow(2, 10, 3)"]:
        ast = Parser(tokenize(expr)).parse()
        report = guard.check_ast(ast)
        status = "✗ 오류" if report.has_error else "✓ 통과"
        print(f"  {status}  '{expr}'")
        for v in report.violations:
            print(f"         {v}")

    # --- IR Guard ---
    print("\n=== [2] IR Guard: 3-주소 코드 검증 ===")
    gen = IRGenerator()
    gen.generate(Parser(tokenize("(3 + 5) * 2")).parse())
    report = guard.check_ir(gen.instrs)
    status = "✗ 오류" if report.has_error else "✓ 통과"
    print(f"  {status}  IR ({len(gen.instrs)}개 명령어)")
    for v in report.violations:
        print(f"         {v}")

    # --- Alloc Guard ---
    print("\n=== [3] Alloc Guard: 레지스터 할당 검증 ===")
    from constraint.register_type_map import RegisterTypeMap
    rtm = RegisterTypeMap()
    # 기존 allocator는 단일 풀을 사용하므로 WARN(REG_TYPE_MISMATCH) 발생 예상
    allocator = RegisterAllocator(rtm.all_regs())
    alloc = allocator.allocate(gen.instrs)
    report = guard.check_allocation(gen.instrs, alloc)
    status = "✗ 오류" if report.has_error else "✓ 통과"
    print(f"  {status}")
    for v in report.violations:
        print(f"         {v}")
