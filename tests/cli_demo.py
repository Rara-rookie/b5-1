"""한 줄 입력 뒤 한 줄 결과를 보여 주는 Mini Redis CLI 데모 스크립트.

실행:
    python tests/cli_demo.py

이 파일은 단위 테스트가 아니라 평가 시연용이다. 실제 REPL과 같은
`tokenize → execute → print` 경로를 사용하되, 사람이 읽기 좋게 각 입력 직후
그 결과를 출력한다. 각 시나리오는 별도 Store를 사용하므로 앞 시나리오의
메모리 설정과 저장 데이터가 다음 시나리오에 영향을 주지 않는다.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

# `python tests/cli_demo.py`로 직접 실행하면 Python은 tests 폴더만 모듈 탐색
# 경로에 넣는다. 부모인 프로젝트 루트를 추가해 mini_redis 패키지를 찾게 한다.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mini_redis.commands import execute
from mini_redis.parser import tokenize
from mini_redis.store import MiniRedisStore


def run_scenario(title: str, commands: Sequence[str]) -> None:
    """각 명령과 그 결과를 실제 CLI처럼 순서대로 출력한다."""
    store = MiniRedisStore()
    print("\n" + "=" * 72)
    print(title)
    for command in commands:
        print("mini-redis> " + command)
        if command.lower() == "exit" or command.lower() == "quit":
            break
        result = execute(store, tokenize(command))
        if result:
            print(result)


def main() -> None:
    run_scenario(
        "1. 문자열 저장·조회·삭제·키 목록",
        [
            'SET user:1 "Alice Kim"',
            "GET user:1",
            "EXISTS user:1",
            "DBSIZE",
            "KEYS",
            "DEL user:1",
            "GET user:1",
            "quit",
        ],
    )

    run_scenario(
        "2. TTL 설정과 조회",
        [
            "SET session:1 abc",
            "EXPIRE session:1 60",
            "TTL session:1",
            "TTL missing:key",
            "EXPIRE session:1 0",
            "GET session:1",
            "quit",
        ],
    )

    run_scenario(
        "3. maxmemory와 LRU 축출",
        [
            "CONFIG SET maxmemory 20",
            "SET a mynameisA",
            "SET b mynameisB",
            "GET a",
            "SET c mynameisC",
            "KEYS",
            "INFO memory",
            "quit",
        ],
    )

    run_scenario(
        "4. 오류 메시지",
        [
            "HELLO",
            "GET",
            "EXPIRE key not-a-number",
            "CONFIG SET maxmemory 3",
            "SET ab cd",
            "quit",
        ],
    )


if __name__ == "__main__":
    main()
