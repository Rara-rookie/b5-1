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


def run_scenario(title: str, commands: Sequence[str | tuple[int, str]]) -> None:
    """각 명령과 그 결과를 실제 CLI처럼 순서대로 출력한다."""
    now = 0
    timed = any(isinstance(step, tuple) for step in commands)
    store = MiniRedisStore(now_fn=lambda: now) if timed else MiniRedisStore()
    print("\n" + "=" * 72)
    print(title)
    for step in commands:
        if isinstance(step, tuple):
            now, command = step
            print(f"[시연 시각 {now}초] ", end="")
        else:
            command = step
        print("mini-redis> " + command)
        if command.lower() == "exit" or command.lower() == "quit":
            break
        result = execute(store, tokenize(command))
        if result:
            print(result)
        entries = {key: store._data.get(key) for key in store._data.keys()}
        GREEN = "\033[92m"
        RESET = "\033[0m"
        print(GREEN + "해시맵 (키 → 값):", entries)
        print(GREEN + "LRU 연결 리스트 (최근 → 오래된 순서):", list(store._lru_list))
        print(GREEN + "TTL 힙 (만료 시각, 키):", store._ttl_heap._data)
        if timed:
            deadlines = {key: store._ttl_map.get(key) for key in store._ttl_map.keys()}
            print("TTL 맵 (키 → 최신 만료 시각):", deadlines)
            print(f"used_memory: {store._used_memory} bytes")
        print(RESET)


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
        "2. TTL 연장 후 예전 힙 기록 정리와 실제 키 만료",
        [
            (100, 'SET user:2 "Bob"'),
            (100, "EXPIRE user:2 3"),
            (101, "EXPIRE user:2 10"),
            (101, "TTL user:2"),
            (104, "GET user:2"),
            (112, "GET user:2"),
            (112, "TTL user:2"),
            "quit",
        ],
    )

    run_scenario(
        "3. maxmemory와 LRU 축출",
        [
            "CONFIG SET maxmemory 30",
            'SET user:1 "Alice"',
            'SET user:2 "Bob"',
            'SET user:3 "Charlie"',
            "GET user:1",
            "INFO memory",
            "KEYS",
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
