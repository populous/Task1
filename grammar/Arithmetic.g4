// ============================================================
// Arithmetic.g4  —  ANTLR4 Grammar
// 4칙연산 (+ - * /) + 함수 호출 (function call)
// 단방향 하향식 파서
//
// 생성 명령:
//   antlr4 -Dlanguage=Python3 Arithmetic.g4
//   또는
//   java -jar antlr-4.13.1-complete.jar -Dlanguage=Python3 Arithmetic.g4
// ============================================================

grammar Arithmetic;

// ── Parser Rules (대문자로 시작 = parser rule) ─────────────────

program
    : expr EOF
    ;

// expr → term (('+' | '-') term)*
expr
    : term ( ( PLUS | MINUS ) term )*
    ;

// term → factor (('*' | '/') factor)*
term
    : factor ( ( MUL | DIV ) factor )*
    ;

// factor → funcCall | '(' expr ')' | NUMBER
factor
    : funcCall             # funcCallExpr
    | LPAREN expr RPAREN   # parenExpr
    | NUMBER               # number
    ;

// funcCall → FUNC_NAME '(' argList? ')'
funcCall
    : FUNC_NAME LPAREN argList? RPAREN
    ;

// argList → expr (',' expr)*
argList
    : expr ( COMMA expr )*
    ;

// ── Lexer Rules (소문자로 시작 = lexer rule) ──────────────────

PLUS    : '+' ;
MINUS   : '-' ;
MUL     : '*' ;
DIV     : '/' ;
LPAREN  : '(' ;
RPAREN  : ')' ;
COMMA   : ',' ;

NUMBER  : [0-9]+ ( '.' [0-9]* )? ;

// 함수 이름: 영문 소문자로 시작하는 식별자 (예: sin, max, pow)
FUNC_NAME : [a-z] [a-zA-Z0-9_]* ;

WS      : [ \t\r\n]+ -> skip ;   // 공백 무시

// ============================================================
// 이 문법으로부터 생성되는 파서 파일 (Python3):
//   ArithmeticLexer.py
//   ArithmeticParser.py
//   ArithmeticListener.py   (트리 순회용)
//   ArithmeticVisitor.py    (AST 빌더용)  <- -visitor 플래그 필요
// ============================================================
