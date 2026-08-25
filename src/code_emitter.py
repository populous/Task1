# code_emitter.py
# Step 4: AST -> EVM-style Stack Bytecode (Contract Order)

from arithmetic_parser import Num, BinOp, FuncCall, tokenize, Parser
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
    name: Optional[str] = None      # only for CALL

    def __str__(self):
        if self.opcode == 'PUSH':
            return f"PUSH {self.operand}"
        if self.opcode == 'CALL':
            return f"CALL {self.name}"
        return self.opcode


class CodeEmitter:
    """
    Walks the AST and emits stack-machine instructions in contract (postfix) order.

    Stack contract per node:
      - After emitting a node, exactly ONE value sits on top of the stack.
      - BinOp:    emit left -> emit right -> emit operator (consumes 2, pushes 1)
      - Num:      PUSH value
      - FuncCall: emit each arg (left to right) -> CALL func_name (consumes N, pushes 1)
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

        if isinstance(node, FuncCall):
            for arg in node.args:
                self.emit(arg)
            self.instructions.append(Bytecode('CALL', name=node.name))
            return

        raise TypeError(f"Unknown AST node: {node}")

    def dump(self) -> None:
        print(f"{'PC':>4}  Instruction")
        print("-" * 22)
        for pc, instr in enumerate(self.instructions):
            print(f"{pc:>4}  {instr}")

    def to_hex(self) -> str:
        """Minimal hex encoding using EVM opcodes.

        Note: PUSH uses a single-byte operand (PUSH1 / 0x60).
        Operand values must fit in one unsigned byte (0–255).
        Larger values would require PUSH2+ encoding which is not
        implemented here; an assertion guards this assumption.
        """
        EVM = {'PUSH': 0x60, 'ADD': 0x01, 'MUL': 0x02, 'SUB': 0x03, 'DIV': 0x04,
               'CALL': 0xf1}
        out = []
        for instr in self.instructions:
            if instr.opcode == 'PUSH':
                operand = instr.operand
                if not isinstance(operand, int):
                    raise TypeError(
                        f"PUSH operand {operand!r} is not an integer; "
                        "non-integer literals are not supported in single-byte encoding"
                    )
                if not (0 <= operand <= 255):
                    raise ValueError(
                        f"PUSH operand {operand} exceeds one-byte range; "
                        "multi-byte PUSH encoding is not supported"
                    )
                out.append(f"{EVM['PUSH']:02x}")
                out.append(f"{operand:02x}")
            elif instr.opcode == 'CALL':
                out.append(f"{EVM['CALL']:02x}")
                # encode function name as 1-byte length + ASCII bytes
                name_bytes = instr.name.encode('ascii')
                out.append(f"{len(name_bytes):02x}")
                out.extend(f"{b:02x}" for b in name_bytes)
            else:
                out.append(f"{EVM[instr.opcode]:02x}")
        return '0x' + ''.join(out)


if __name__ == '__main__':
    for expr in [
        "(3 + 5) * 2 - 8 / 4",
        "sin(30)",
        "max(3 + 1, 2 * 5)",
        "pow(2, 10) + 1",
    ]:
        ast = Parser(tokenize(expr)).parse()
        emitter = CodeEmitter()
        emitter.emit(ast)
        print(f"Expression : {expr}")
        emitter.dump()
        print(f"\nHex bytecode: {emitter.to_hex()}\n")
