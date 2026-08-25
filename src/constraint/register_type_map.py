# constraint/register_type_map.py
# ============================================================
# 레지스터 유형 분류 맵 (Register Type Map)
#
# operator_contract.json 의 register_banks / reg_type 필드를 읽어
# 각 연산자·함수의 결과가 어느 레지스터 뱅크에 할당돼야 하는지 결정한다.
#
# 사용:
#   from constraint.register_type_map import RegisterTypeMap
#   rtm = RegisterTypeMap()
#   rtm.bank_for_op('+')       -> ['R0','R1','R2','R3']
#   rtm.bank_for_func('sin')   -> ['F0','F1','F2','F3']
#   rtm.reg_type_of_op('+')    -> 'INT'
#   rtm.reg_type_of_func('max')-> 'CALL'
# ============================================================

from __future__ import annotations

import json
import os
from typing import Dict, List, Optional


class RegisterTypeMap:
    """
    operator_contract.json 에서 레지스터 유형 정보를 로드하고
    연산자 / 함수명 → 레지스터 뱅크 변환 서비스를 제공한다.
    """

    def __init__(self, contract_path: Optional[str] = None):
        if contract_path is None:
            # src/constraint/ 기준으로 ../../contract/ 경로 자동 탐색
            _here = os.path.dirname(os.path.abspath(__file__))
            contract_path = os.path.join(_here, '..', '..', 'contract', 'operator_contract.json')

        with open(contract_path, 'r', encoding='utf-8') as f:
            contract = json.load(f)

        # 레지스터 뱅크: {'INT': ['R0',...], 'FLOAT': ['F0',...], ...}
        self.banks: Dict[str, List[str]] = contract.get('register_banks', {})

        # 연산자 심볼 → reg_type 매핑: {'+': 'INT', ...}
        self._op_type: Dict[str, str] = {
            entry['symbol']: entry['reg_type']
            for entry in contract.get('operators', [])
            if 'reg_type' in entry
        }

        # 함수명 → reg_type 매핑: {'sin': 'FLOAT', 'max': 'CALL', ...}
        self._func_type: Dict[str, str] = {
            entry['name']: entry['reg_type']
            for entry in contract.get('functions', [])
            if 'reg_type' in entry
        }

        # 연산자 심볼 → arity 매핑: {'+': 2, ...}
        self._op_arity: Dict[str, int] = {
            entry['symbol']: entry.get('arity', 2)
            for entry in contract.get('operators', [])
        }

        # 함수명 → arity 매핑: {'sin': 1, 'max': 2, ...}
        self._func_arity: Dict[str, int] = {
            entry['name']: entry.get('arity', -1)
            for entry in contract.get('functions', [])
        }

    # ── 레지스터 유형 조회 ─────────────────────────────────────

    def reg_type_of_op(self, symbol: str) -> Optional[str]:
        """연산자 심볼의 레지스터 유형을 반환한다."""
        return self._op_type.get(symbol)

    def reg_type_of_func(self, name: str) -> Optional[str]:
        """함수명의 레지스터 유형을 반환한다."""
        return self._func_type.get(name)

    # ── 레지스터 뱅크 조회 ─────────────────────────────────────

    def bank_for_op(self, symbol: str) -> List[str]:
        """연산자 심볼에 대응하는 물리 레지스터 뱅크를 반환한다."""
        reg_type = self._op_type.get(symbol)
        if reg_type is None:
            raise KeyError(f"[RegisterTypeMap] 미등록 연산자: '{symbol}'")
        return list(self.banks.get(reg_type, []))

    def bank_for_func(self, name: str) -> List[str]:
        """함수명에 대응하는 물리 레지스터 뱅크를 반환한다."""
        reg_type = self._func_type.get(name)
        if reg_type is None:
            raise KeyError(f"[RegisterTypeMap] 미등록 함수: '{name}'")
        return list(self.banks.get(reg_type, []))

    def bank_for_type(self, reg_type: str) -> List[str]:
        """레지스터 유형명으로 뱅크를 반환한다."""
        if reg_type not in self.banks:
            raise KeyError(f"[RegisterTypeMap] 미정의 레지스터 유형: '{reg_type}'")
        return list(self.banks[reg_type])

    # ── Arity 조회 ─────────────────────────────────────────────

    def arity_of_op(self, symbol: str) -> int:
        """연산자 심볼의 인자 수를 반환한다."""
        return self._op_arity.get(symbol, 2)

    def arity_of_func(self, name: str) -> int:
        """함수명의 인자 수를 반환한다. 미등록 함수는 -1(검증 불가)."""
        return self._func_arity.get(name, -1)

    # ── 등록 여부 조회 ─────────────────────────────────────────

    def is_registered_op(self, symbol: str) -> bool:
        return symbol in self._op_type

    def is_registered_func(self, name: str) -> bool:
        return name in self._func_type

    # ── 전체 뱅크 목록 ─────────────────────────────────────────

    def all_banks(self) -> Dict[str, List[str]]:
        return dict(self.banks)

    def all_regs(self) -> List[str]:
        """모든 유형의 물리 레지스터를 평탄화하여 반환한다."""
        result = []
        for regs in self.banks.values():
            result.extend(regs)
        return result


# ── 단독 실행 (조회 테스트) ────────────────────────────────────
if __name__ == '__main__':
    rtm = RegisterTypeMap()

    print("=== 레지스터 뱅크 ===")
    for reg_type, regs in rtm.all_banks().items():
        print(f"  {reg_type:<8}: {regs}")

    print("\n=== 연산자 → 유형 / 뱅크 ===")
    for sym in ['+', '-', '*', '/']:
        rtype = rtm.reg_type_of_op(sym)
        bank  = rtm.bank_for_op(sym)
        arity = rtm.arity_of_op(sym)
        print(f"  '{sym}'  reg_type={rtype:5}  arity={arity}  bank={bank}")

    print("\n=== 함수 → 유형 / 뱅크 ===")
    for fn in ['sin', 'cos', 'max', 'min', 'pow']:
        rtype = rtm.reg_type_of_func(fn)
        bank  = rtm.bank_for_func(fn)
        arity = rtm.arity_of_func(fn)
        print(f"  {fn:<4}  reg_type={rtype:6}  arity={arity}  bank={bank}")

    print("\n=== 미등록 연산자 테스트 ===")
    print(f"  '%' 등록 여부: {rtm.is_registered_op('%')}")
    print(f"  '+' 등록 여부: {rtm.is_registered_op('+')}")
