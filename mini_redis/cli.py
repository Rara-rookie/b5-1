from .commands import execute
from .parser import tokenize
from .store import MiniRedisStore


def run() -> None:
    """Mini Redis 명령을 반복해서 읽고 실행하는 REPL을 시작한다.

    사용자가 한 줄을 입력할 때마다 토큰화 후 실행 결과를 출력한다.
    exit 또는 quit을 입력하면 루프를 종료하고,
    입력 스트림이 끝나면 줄바꿈을 한 번 출력한 뒤 종료한다.
    """
    store = MiniRedisStore()

    while True:
        try:
            line = input("mini-redis> ")
        except EOFError:
            print()
            break

        stripped = line.strip()
        if stripped.lower() == "exit" or stripped.lower() == "quit":
            break

        tokens = tokenize(line)
        result = execute(store, tokens)
        if result != "":
            print(result)
