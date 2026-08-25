# ir_generator.py
# Step 2: AST -> Three-Address Code (IR)

from arithmetic_parser import Num, BinOp, tokenize, Parser
from dataclasses import dataclass
from typing import Optional


@dataclass
class IRInstr:
    result: str
    op: Optional[str]   # '+' '-' '*' '/'  (None = simple assign)
    arg1: str
    arg2: Optional[str]

    def __str__(self):
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

        raise TypeError(f"Unknown node: {node}")

    def dump(self):
        for instr in self.instrs:
            print(instr)


if __name__ == '__main__':
    expr = "(3 + 5) * 2 - 8 / 4"
    ast  = Parser(tokenize(expr)).parse()

    gen = IRGenerator()
    result = gen.generate(ast)
    print(f"Expression : {expr}")
    print(f"Result in  : {result}")
    print("-" * 30)
    gen.dump()
