"""실제 CLI 입출력을 보여 주는 Mini Redis 데모 스크립트.

실행:
    python tests/cli_demo.py

이 파일은 단위 테스트가 아니라 평가 시연용이다. 각 시나리오를 별도의
`python -m mini_redis` 프로세스로 실행하므로, 앞 시나리오의 메모리 설정과
저장 데이터가 다음 시나리오에 영향을 주지 않는다.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence


def run_scenario(title: str, commands: Sequence[str]) -> None:
    """명령 묶음을 실제 REPL에 전달하고 입력과 출력을 화면에 표시한다."""
    input_text = "\n".join(commands) + "\n"
    completed = subprocess.run(
        [sys.executable, "-m", "mini_redis"],
        input=input_text,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    print("\n" + "=" * 72)
    print(title)
    print("- 입력 명령")
    for command in commands:
        print("  " + command)
    print("- 실제 CLI 출력")
    print(completed.stdout.rstrip())

    if completed.stderr:
        print("- stderr")
        print(completed.stderr.rstrip())
    if completed.returncode != 0:
        raise SystemExit("CLI 실행 실패: exit code " + str(completed.returncode))


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
            "SET a 123456789",
            "SET b 123456789",
            "GET a",
            "SET c 123456789",
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
