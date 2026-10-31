class RedisError(Exception):
    """Mini Redis CLI 에 그대로 출력되는 에러 메시지의 기반 예외이다."""

    def __init__(self, message: str):
        """출력할 전체 메시지(`(error) ...`)를 예외 메시지로 저장한다."""
        super().__init__(message)


class UnknownCommandError(RedisError):
    """지원하지 않는 명령을 받았을 때 발생한다."""

    def __init__(self, command: str):
        """사용자가 입력한 명령 이름을 그대로 넣어 표준 unknown command 메시지를 만든다."""
        super().__init__("(error) ERR unknown command '" + command + "'")


class WrongArgsError(RedisError):
    """명령의 인자 개수가 맞지 않을 때 발생한다."""

    def __init__(self, command: str):
        """사용자가 입력한 명령 이름을 넣어 표준 wrong number of arguments 메시지를 만든다."""
        super().__init__("(error) ERR wrong number of arguments for '" + command + "' command")


class NotIntegerError(RedisError):
    """정수 인자를 해석할 수 없거나 허용 범위를 벗어났을 때 발생한다."""

    def __init__(self) -> None:
        """고정된 표준 정수 파싱 실패 메시지를 만든다."""
        super().__init__("(error) ERR value is not an integer or out of range")


class OOMError(RedisError):
    """쓰기가 maxmemory 제한을 넘어 저장할 수 없을 때 발생한다."""

    def __init__(self) -> None:
        """고정된 표준 OOM 메시지를 만든다."""
        super().__init__("(error) OOM command not allowed when used_memory > 'maxmemory'")
