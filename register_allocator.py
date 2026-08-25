# register_allocator.py
# Step 3: IR temporaries -> Physical Registers (Linear Scan)
#
# Operator aliases are resolved at the register layer (not in grammar).
# Alias mappings are loaded from operator_contract.yaml.

import os
import json
import yaml

from ir_generator import IRInstr, IRGenerator
from arithmetic_parser import tokenize, Parser

PHYSICAL_REGS = ['R0', 'R1', 'R2', 'R3']

# Load operator alias contract — JSON preferred, YAML as fallback
_DIR = os.path.dirname(os.path.abspath(__file__))
_CONTRACT_JSON = os.path.join(_DIR, 'operator_contract.json')
_CONTRACT_YAML = os.path.join(_DIR, 'operator_contract.yaml')

def _load_op_alias(json_path: str, yaml_path: str) -> dict:
    if os.path.exists(json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            contract = json.load(f)
    else:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            contract = yaml.safe_load(f)
    return {entry['symbol']: entry['alias'] for entry in contract['operators']}

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
        for arg in (instr.arg1, instr.arg2):
            if arg and arg.startswith('t'):
                if arg not in intervals:
                    intervals[arg] = [idx, idx]
                intervals[arg][1] = max(intervals[arg][1], idx)

    return {k: (v[0], v[1]) for k, v in intervals.items()}


class RegisterAllocator:
    def __init__(self, regs: list):
        self.regs       = list(regs)
        self.free_regs  = list(regs)
        self.active     : dict = {}   # temp -> reg currently holding it
        self.allocation : dict = {}   # temp -> reg (or 'MEM[n]')
        self.spill_slot = 0

    def _spill_one(self, intervals: dict) -> str:
        """Spill the temp whose interval ends latest."""
        victim = max(self.active, key=lambda t: intervals[t][1])
        reg = self.active.pop(victim)
        slot = f"MEM[{self.spill_slot}]"
        self.spill_slot += 1
        self.allocation[victim] = slot
        print(f"  !! SPILL {victim} from {reg} -> {slot}")
        return reg

    def allocate(self, instrs: list) -> dict:
        intervals = compute_liveness(instrs)
        for temp, (start, end) in sorted(intervals.items(), key=lambda x: x[1][0]):
            # expire temps whose live interval has ended
            expired = [t for t, r in self.active.items()
                       if intervals[t][1] < start]
            for t in expired:
                self.free_regs.append(self.active.pop(t))

            if self.free_regs:
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
        if instr.op:
            alias = OP_ALIAS.get(instr.op, instr.op)   # resolve alias
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
    print(f"Registers  : {PHYSICAL_REGS}")
    print("-" * 40)

    allocator = RegisterAllocator(PHYSICAL_REGS)
    alloc = allocator.allocate(gen.instrs)

    print(f"\nOperator aliases (register layer):")
    for sym, alias in OP_ALIAS.items():
        print(f"  '{sym}'  ->  {alias}")

    print("\nTemp -> Register mapping:")
    for temp, reg in alloc.items():
        print(f"  {temp:4s} -> {reg}")

    print("\nAllocated IR (with aliases):")
    for line in apply_allocation(gen.instrs, alloc):
        print(" ", line)
