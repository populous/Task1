# register_allocator.py
# Step 3: IR temporaries -> Physical Registers (Linear Scan)

from ir_generator import IRInstr, IRGenerator
from arithmetic_parser import tokenize, Parser

PHYSICAL_REGS = ['R0', 'R1', 'R2', 'R3']


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
    result = []
    for instr in instrs:
        dest = alloc.get(instr.result, instr.result)
        a1   = alloc.get(instr.arg1,   instr.arg1) if instr.arg1 else ''
        a2   = alloc.get(instr.arg2,   instr.arg2) if instr.arg2 else ''
        if instr.op:
            result.append(f"{dest} = {a1} {instr.op} {a2}")
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

    print("\nTemp -> Register mapping:")
    for temp, reg in alloc.items():
        print(f"  {temp:4s} -> {reg}")

    print("\nAllocated IR:")
    for line in apply_allocation(gen.instrs, alloc):
        print(" ", line)
