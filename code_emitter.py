# code_emitter.py
# Step 4: AST -> EVM-style Stack Bytecode (Contract Order)

from arithmetic_parser import Num, BinOp, tokenize, Parser
from dataclasses import dataclass
from typing import Optional

OP_TO_OPCODE = {
    '+': 'ADD',
    '-': 'SUB',
    '*': 'MUL',
    '/': 'DIV',
}


@dataclass
class Bytecode:
    opcode: str
    operand: Optional[int] = None   # only for PUSH

    def __str__(self):
        if self.operand is not None:
            return f"PUSH {self.operand}"
        return self.opcode


class CodeEmitter:
    """
    Walks the AST and emits stack-machine instructions in contract (postfix) order.

    Stack contract per node:
      - After emitting a node, exactly ONE value sits on top of the stack.
      - BinOp: emit left -> emit right -> emit operator (consumes 2, pushes 1)
      - Num:   PUSH value
    """
    def __init__(self):
        self.instructions: list = []

    def emit(self, node) -> None:
        if isinstance(node, Num):
            v = int(node.value) if node.value == int(node.value) else node.value
            self.instructions.append(Bytecode('PUSH', v))
            return

        if isinstance(node, BinOp):
            self.emit(node.left)
            self.emit(node.right)
            opcode = OP_TO_OPCODE[node.op]
            self.instructions.append(Bytecode(opcode))
            return

        raise TypeError(f"Unknown AST node: {node}")

    def dump(self) -> None:
        print(f"{'PC':>4}  Instruction")
        print("-" * 22)
        for pc, instr in enumerate(self.instructions):
            print(f"{pc:>4}  {instr}")

    def to_hex(self) -> str:
        """Minimal hex encoding using EVM opcodes."""
        EVM = {'PUSH': 0x60, 'ADD': 0x01, 'MUL': 0x02, 'SUB': 0x03, 'DIV': 0x04}
        out = []
        for instr in self.instructions:
            if instr.opcode == 'PUSH':
                out.append(f"{EVM['PUSH']:02x}")
                out.append(f"{instr.operand:02x}")
            else:
                out.append(f"{EVM[instr.opcode]:02x}")
        return '0x' + ''.join(out)


if __name__ == '__main__':
    expr = "(3 + 5) * 2 - 8 / 4"
    ast  = Parser(tokenize(expr)).parse()

    emitter = CodeEmitter()
    emitter.emit(ast)

    print(f"Expression : {expr}")
    print(f"Expected   : {(3+5)*2 - 8//4}  (= {(3+5)*2} - {8//4})\n")
    emitter.dump()
    print(f"\nHex bytecode: {emitter.to_hex()}")
