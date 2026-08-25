# ir_generator.py
# Step 2: AST -> Three-Address Code (IR)

from arithmetic_parser import Num, BinOp, FuncCall, tokenize, Parser
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class IRInstr:
    result: str
    op: Optional[str]   # '+' '-' '*' '/'  or 'call'  (None = simple assign)
    arg1: str
    arg2: Optional[str]
    # extra arguments beyond arg1/arg2 for multi-arg function calls
    extra_args: List[str] = field(default_factory=list)

    def __str__(self):
        if self.op == 'call':
            all_args = [self.arg1] + list(filter(None, [self.arg2])) + self.extra_args
            return f"{self.result} = {self.arg1}({', '.join(all_args[1:])})"
        if self.op:
            return f"{self.result} = {self.arg1} {self.op} {self.arg2}"
        return f"{self.result} = {self.arg1}"


class IRGenerator:
    def __init__(self):
        self.instrs: list = []
        self._counter = 0

    def _new_temp(self) -> str:
        self._counter += 1
        return f"t{self._counter}"

    def generate(self, node) -> str:
        """Recursively emit instructions; returns the temp name holding the result."""
        if isinstance(node, Num):
            temp = self._new_temp()
            val = int(node.value) if node.value == int(node.value) else node.value
            self.instrs.append(IRInstr(temp, None, str(val), None))
            return temp

        if isinstance(node, BinOp):
            left  = self.generate(node.left)
            right = self.generate(node.right)
            temp  = self._new_temp()
            self.instrs.append(IRInstr(temp, node.op, left, right))
            return temp

        if isinstance(node, FuncCall):
            # evaluate each argument first
            arg_temps = [self.generate(arg) for arg in node.args]
            temp = self._new_temp()
            self.instrs.append(_FuncCallInstr(temp, node.name, arg_temps))
            return temp

        raise TypeError(f"Unknown node: {node}")

    def dump(self):
        for instr in self.instrs:
            print(instr)


class _FuncCallInstr:
    """Specialised IR instruction for function calls."""
    def __init__(self, result: str, func: str, args: list):
        self.result = result
        self.op = 'call'
        self.arg1 = func
        self.arg2 = None
        self.extra_args = args
        self._func = func
        self._args = args

    def __str__(self):
        args_str = ', '.join(self._args)
        return f"{self.result} = {self._func}({args_str})"

    def __repr__(self):
        return str(self)


if __name__ == '__main__':
    for expr in [
        "(3 + 5) * 2 - 8 / 4",
        "sin(30)",
        "max(3 + 1, 2 * 5)",
        "pow(2, 10) + 1",
    ]:
        ast = Parser(tokenize(expr)).parse()
        gen = IRGenerator()
        result = gen.generate(ast)
        print(f"Expression : {expr}")
        print(f"Result in  : {result}")
        print("-" * 30)
        gen.dump()
        print()
