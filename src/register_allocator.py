# register_allocator.py
# Step 3: IR temporaries -> Physical Registers (Linear Scan)
#
# Operator aliases are resolved at the register layer (not in grammar).
# Alias mappings are loaded from operator_contract.json (via RegisterTypeMap).
# 레지스터 유형별 뱅크(INT/FLOAT/CALL)는 RegisterTypeMap 이 제공한다.

import os
import json
import logging
import sys
try:
    import yaml as _yaml
except ImportError:
    _yaml = None

from ir_generator import IRInstr, IRGenerator
from arithmetic_parser import tokenize, Parser

# constraint 패키지 경로 추가
_SRC = os.path.dirname(os.path.abspath(__file__))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from constraint.register_type_map import RegisterTypeMap as _RTM

# 레지스터 유형 맵 (singleton)
_rtm = _RTM()

# 하위 호환: 기존 코드에서 PHYSICAL_REGS 를 직접 참조하는 경우를 위해 유지
# (INT 뱅크 기준 — 필요 시 _rtm.all_regs() 로 교체)
PHYSICAL_REGS = _rtm.bank_for_type('INT')

_DIR = os.path.dirname(os.path.abspath(__file__))
_CONTRACT_JSON = os.path.join(_SRC, '..', 'contract', 'operator_contract.json')
_CONTRACT_YAML = os.path.join(_SRC, '..', 'contract', 'operator_contract.yaml')

def _load_op_alias(json_path: str, yaml_path: str) -> dict:
    if os.path.exists(json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            contract = json.load(f)
    else:
        if _yaml is None:
            raise ImportError("PyYAML is required to load operator_contract.yaml")
        with open(yaml_path, 'r', encoding='utf-8') as f:
            contract = _yaml.safe_load(f)
    # Support both legacy 'alias' (str) and new 'aliases' (list); aliases[0] = primary
    result = {}
    for entry in contract['operators']:
        if 'aliases' in entry:
            result[entry['symbol']] = entry['aliases']
        else:
            result[entry['symbol']] = [entry['alias']]
    return result

OP_ALIAS: dict = _load_op_alias(_CONTRACT_JSON, _CONTRACT_YAML)


def compute_liveness(instrs: list) -> dict:
    """Returns {temp: (first_def, last_use)} live intervals."""
    intervals: dict = {}

    for idx, instr in enumerate(instrs):
        # definition
        if instr.result not in intervals:
            intervals[instr.result] = [idx, idx]
        else:
            intervals[instr.result][0] = min(intervals[instr.result][0], idx)

        # uses
        use_args = [instr.arg1, instr.arg2] + list(getattr(instr, 'extra_args', []))
        for arg in use_args:
            if arg and arg.startswith('t'):
                if arg not in intervals:
                    intervals[arg] = [idx, idx]
                intervals[arg][1] = max(intervals[arg][1], idx)

    return {k: (v[0], v[1]) for k, v in intervals.items()}


class RegisterAllocator:
    """
    Linear Scan 레지스터 할당기.

    type_aware=True 이면 RegisterTypeMap 을 사용해 각 임시변수의
    결과 유형(INT/FLOAT/CALL)에 맞는 뱅크에서 레지스터를 할당한다.
    type_aware=False(기본) 이면 단일 regs 풀을 사용한다 (하위 호환).
    """

    def __init__(self, regs: list, type_aware: bool = False):
        self.regs        = list(regs)
        self.free_regs   = list(regs)
        self.active      : dict = {}   # temp -> reg currently holding it
        self.allocation  : dict = {}   # temp -> reg (or 'MEM[n]')
        self.spill_slot  = 0
        self.type_aware  = type_aware
        # 유형 인식 모드: 뱅크별 여유 레지스터 풀 관리
        if type_aware:
            self._free_banks: dict = {
                k: list(v) for k, v in _rtm.all_banks().items()
            }

    def _spill_one(self, intervals: dict) -> str:
        """Spill the temp whose interval ends latest."""
        if not self.active:
            slot = f"MEM[{self.spill_slot}]"
            self.spill_slot += 1
            return slot
        victim = max(self.active, key=lambda t: intervals[t][1])
        reg = self.active.pop(victim)
        slot = f"MEM[{self.spill_slot}]"
        self.spill_slot += 1
        self.allocation[victim] = slot
        logging.debug("SPILL %s from %s -> %s", victim, reg, slot)
        return reg

    def _pick_reg(self, temp: str, instr_map: dict, intervals: dict) -> str:
        """유형 인식 모드에서 temp 에 맞는 뱅크를 선택하여 레지스터를 반환한다."""
        instr = instr_map.get(temp)
        reg_type = None
        if instr:
            if instr.op == 'call':
                # arg1이 함수명
                reg_type = _rtm.reg_type_of_func(instr.arg1)
            elif instr.op:
                reg_type = _rtm.reg_type_of_op(instr.op)

        bank_key = reg_type if (reg_type and reg_type in self._free_banks) else 'INT'

        if bank_key and self._free_banks[bank_key]:
            return self._free_banks[bank_key].pop(0)

        # 대상 뱅크가 없거나 가득 찬 경우 → 스필
        return self._spill_one(intervals)

    def _release_reg(self, reg: str) -> None:
        """반환된 레지스터를 해당 뱅크의 여유 풀에 돌려놓는다."""
        if not self.type_aware:
            self.free_regs.append(reg)
            return
        for btype, bregs in _rtm.banks.items():
            if reg in bregs:
                self._free_banks[btype].append(reg)
                return

    def allocate(self, instrs: list) -> dict:
        # temp → 그 temp를 정의하는 IRInstr 매핑 (유형 인식용)
        instr_map: dict = {instr.result: instr for instr in instrs if instr.result}
        intervals = compute_liveness(instrs)

        for temp, (start, end) in sorted(intervals.items(), key=lambda x: x[1][0]):
            # 만료된 temp 해제
            expired = [t for t, r in self.active.items()
                       if intervals[t][1] < start]
            for t in expired:
                self._release_reg(self.active.pop(t))

            if self.type_aware:
                reg = self._pick_reg(temp, instr_map, intervals)
            elif self.free_regs:
                reg = self.free_regs.pop(0)
            else:
                reg = self._spill_one(intervals)

            self.active[temp] = reg
            self.allocation[temp] = reg

        return self.allocation


def apply_allocation(instrs: list, alloc: dict) -> list:
    """
    Rewrite IR instructions with physical register names.
    Operator symbols are replaced by their mnemonic aliases (OP_ALIAS)
    at this register layer — the grammar remains unchanged.
    """
    result = []
    for instr in instrs:
        dest = alloc.get(instr.result, instr.result)
        a1   = alloc.get(instr.arg1,   instr.arg1) if instr.arg1 else ''
        a2   = alloc.get(instr.arg2,   instr.arg2) if instr.arg2 else ''
        if instr.op == 'call':
            extra = getattr(instr, 'extra_args', [])
            mapped_args = ', '.join(alloc.get(a, a) for a in extra)
            result.append(f"{dest} = {a1}({mapped_args})")
        elif instr.op:
            alias = OP_ALIAS.get(instr.op, [instr.op])[0]   # aliases[0] = primary
            result.append(f"{dest} = {alias}({a1}, {a2})")
        else:
            result.append(f"{dest} = {a1}")
    return result


if __name__ == '__main__':
    expr = "(3 + 5) * 2 - 8 / 4"
    ast  = Parser(tokenize(expr)).parse()

    gen = IRGenerator()
    gen.generate(ast)

    print(f"Expression : {expr}")
    print("-" * 50)

    # ── 기존 모드 (단일 풀) ──────────────────────────────────
    print(f"\n[기존 모드] Registers: {PHYSICAL_REGS}")
    allocator = RegisterAllocator(PHYSICAL_REGS)
    alloc = allocator.allocate(gen.instrs)

    print(f"\nOperator aliases (register layer):")
    for sym, aliases in OP_ALIAS.items():
        print(f"  '{sym}'  ->  {aliases}  (primary: {aliases[0]})")

    print("\nTemp -> Register mapping:")
    for temp, reg in alloc.items():
        print(f"  {temp:4s} -> {reg}")

    print("\nAllocated IR (with aliases):")
    for line in apply_allocation(gen.instrs, alloc):
        print(" ", line)

    # ── 유형 인식 모드 ────────────────────────────────────────
    print(f"\n{'─'*50}")
    print("[유형 인식 모드] 레지스터 뱅크:")
    for btype, bregs in _rtm.all_banks().items():
        print(f"  {btype:<8}: {bregs}")

    gen2 = IRGenerator()
    gen2.generate(ast)
    allocator2 = RegisterAllocator(_rtm.all_regs(), type_aware=True)
    alloc2 = allocator2.allocate(gen2.instrs)

    print("\nTemp -> Register mapping (유형 인식):")
    for temp, reg in alloc2.items():
        print(f"  {temp:4s} -> {reg}")

    print("\nAllocated IR (유형 인식, with aliases):")
    for line in apply_allocation(gen2.instrs, alloc2):
        print(" ", line)
