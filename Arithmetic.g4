// ============================================================
// Arithmetic.g4  —  ANTLR4 Grammar
// 4칙연산 (+ - * /) 단방향 하향식 파서
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

// factor → '(' expr ')' | NUMBER
factor
    : LPAREN expr RPAREN   # parenExpr
    | NUMBER               # number
    ;

// ── Lexer Rules (소문자로 시작 = lexer rule) ──────────────────

PLUS   : '+' ;
MINUS  : '-' ;
MUL    : '*' ;
DIV    : '/' ;
LPAREN : '(' ;
RPAREN : ')' ;

NUMBER : [0-9]+ ( '.' [0-9]* )? ;

WS     : [ \t\r\n]+ -> skip ;   // 공백 무시

// ============================================================
// 이 문법으로부터 생성되는 파서 파일 (Python3):
//   ArithmeticLexer.py
//   ArithmeticParser.py
//   ArithmeticListener.py   (트리 순회용)
//   ArithmeticVisitor.py    (AST 빌더용)  <- -visitor 플래그 필요
// ============================================================
