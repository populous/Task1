# Arithmetic Expression Compiler Pipeline

산술식 문자열을 입력받아 **EVM 스타일 바이트코드**까지 생성하는  
소형 컴파일러 파이프라인입니다.  
코드 개발의 일반 과정(명세 → 어휘분석 → 구문분석 → IR생성 → 자원할당 → 코드방출)을  
추상 기반 클래스(ABC)로 추상화하고, 각 단계를 독립 모듈로 구현합니다.

---

## 파이프라인 개요

```
소스 문자열
  │
  ▼  [Stage 1: Lexer]          src/arithmetic_parser.py — 토크나이저
  │  토큰 스트림
  │
  ▼  [Stage 2: Parser]         src/arithmetic_parser.py — 재귀 하강 파서
  │  AST (Num / BinOp / FuncCall)
  │
  ▼  [Stage 3: IRGen]          src/ir_generator.py — 3-주소 코드 생성
  │  Three-Address Code (t1 = a op b / t2 = f(t1))
  │
  ▼  [Stage 4: Allocator]      src/register_allocator.py — Linear Scan
  │  레지스터 할당된 IR (R0 = Add(R1, R2) …)
  │
  ▼  [Stage 5: Emitter]        src/code_emitter.py — 스택 머신 바이트코드
  │  PUSH / ADD / SUB / MUL / DIV / CALL …
  │
  ▼  16진수 바이트코드 (0x…)
```

---

## 지원 문법

| 구성 요소 | 예시 |
|-----------|------|
| 사칙연산  | `3 + 5`, `8 / 4`, `(3 + 5) * 2` |
| 함수 호출 | `sin(30)`, `max(3+1, 2*5)`, `pow(2,10)` |
| 중첩 표현 | `pow(2, 10) + max(1, 3 * 2)` |

EBNF 명세: [`grammar/ebnf_spec.txt`](grammar/ebnf_spec.txt)  
ANTLR4 문법: [`grammar/Arithmetic.g4`](grammar/Arithmetic.g4)

---

## 추상화 구조 (`src/pipeline_abc.py`)

```
BaseLexer       → tokenize(source) → List[Token]
BaseParser      → parse(tokens)    → AST
BaseIRGen       → generate(ast)    → List[IRInstr]
BaseAllocator   → allocate(ir)     → List[str]
BaseEmitter     → emit(ast) / dump() / serialize()
BasePipeline    → run(source)      → PipelineResult
```

구체 구현은 [`src/pipeline.py`](src/pipeline.py) 의 `ArithmeticPipeline` 참조.

---

## 폴더 구성

```
Task1/
├── grammar/                        # 문법 명세
│   ├── Arithmetic.g4               # ANTLR4 문법
│   └── ebnf_spec.txt               # EBNF 명세
│
├── contract/                       # 연산자 계약 명세
│   ├── operator_contract.json
│   └── operator_contract.yaml
│
├── src/                            # Python 소스 코드
│   ├── arithmetic_parser.py        # 어휘분석 + 구문분석 (Stage 1–2)
│   ├── antlr_parser_bridge.py      # ANTLR4 파서 연동 (Stage 1–2 대안)
│   ├── ir_generator.py             # IR 생성 (Stage 3)
│   ├── register_allocator.py       # 레지스터 할당 (Stage 4)
│   ├── code_emitter.py             # 바이트코드 방출 (Stage 5)
│   ├── pipeline_abc.py             # 추상 기반 클래스 정의
│   └── pipeline.py                 # 전체 파이프라인 조립 및 실행
│
└── README.md
```

---

## 실행

```bash
# 전체 파이프라인 실행 (4가지 예제 표현식)
python src/pipeline.py

# 개별 단계 실행
python src/arithmetic_parser.py     # AST 출력
python src/ir_generator.py          # IR 출력
python src/register_allocator.py    # 레지스터 할당 결과
python src/code_emitter.py          # 바이트코드 출력
```

---

## 예시 출력

입력: `max(3 + 1, 2 * 5)`

```
[Stage 3] IR:
    t1 = 3
    t2 = 1
    t3 = t1 + t2
    t4 = 2
    t5 = 5
    t6 = t4 * t5
    t7 = max(t3, t6)

[Stage 4] Allocated IR:
    R0 = Add(R0, R1)
    R1 = Mul(R3, R0)
    R2 = call(max, )

[Stage 5] Bytecode: 0x60036001016002600502f1036d6178
```
