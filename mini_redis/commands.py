from .errors import NotIntegerError, RedisError, UnknownCommandError, WrongArgsError


def execute(store: 'MiniRedisStore', tokens: list[str]) -> str:
    """토큰화된 CLI 명령을 해석해 저장소 메서드로 라우팅하고 Redis 형식의 문자열 응답을 반환한다.

    명령 파싱, 인자 수 검증, 출력 포맷, 예외 문자열화가 모두 이 함수에 모여 있는 이유는
    저장소 구현이 데이터 처리에만 집중하고 CLI 계층은 사용자와의 계약을 일관되게 유지하도록 분리하기 위해서이다.
    """
    try:
        if len(tokens) == 0:
            return ""

        command = tokens[0]
        upper_command = command.upper()

        if upper_command == "SET":
            if len(tokens) != 3:
                raise WrongArgsError(command)
            store.set(tokens[1], tokens[2])
            return "OK"

        if upper_command == "GET":
            if len(tokens) != 2:
                raise WrongArgsError(command)
            value = store.get(tokens[1])
            if value is None:
                return "(nil)"
            return '"' + value + '"'

        if upper_command == "DEL":
            if len(tokens) != 2:
                raise WrongArgsError(command)
            result = store.delete(tokens[1])
            return "(integer) " + str(result)

        if upper_command == "EXISTS":
            if len(tokens) != 2:
                raise WrongArgsError(command)
            result = store.exists(tokens[1])
            return "(integer) " + str(result)

        if upper_command == "DBSIZE":
            if len(tokens) != 1:
                raise WrongArgsError(command)
            result = store.dbsize()
            return "(integer) " + str(result)

        if upper_command == "KEYS":
            if len(tokens) != 1:
                raise WrongArgsError(command)
            keys = store.keys()
            if len(keys) == 0:
                return "(empty array)"
            lines: list[str] = []
            index = 1
            for key in keys:
                lines.append(str(index) + '. "' + key + '"')
                index += 1
            return "\n".join(lines)

        if upper_command == "CONFIG":
            if len(tokens) != 4:
                raise WrongArgsError(command)
            if tokens[1].upper() != "SET" or tokens[2].lower() != "maxmemory":
                raise UnknownCommandError(command)
            bytes_limit = _parse_int(tokens[3])
            if bytes_limit < 0:
                raise NotIntegerError()
            store.set_maxmemory(bytes_limit)
            return "OK"

        if upper_command == "INFO":
            if len(tokens) != 2:
                raise WrongArgsError(command)
            if tokens[1].lower() != "memory":
                raise UnknownCommandError(command)
            used_memory, maxmemory, evicted_keys = store.info_memory()
            return (
                "used_memory:" + str(used_memory) + "\n"
                + "maxmemory:" + str(maxmemory) + "\n"
                + "evicted_keys:" + str(evicted_keys)
            )

        if upper_command == "EXPIRE":
            if len(tokens) != 3:
                raise WrongArgsError(command)
            seconds = _parse_int(tokens[2])
            result = store.expire(tokens[1], seconds)
            return "(integer) " + str(result)

        if upper_command == "TTL":
            if len(tokens) != 2:
                raise WrongArgsError(command)
            result = store.ttl(tokens[1])
            return "(integer) " + str(result)

        raise UnknownCommandError(command)
    except RedisError as error:
        return str(error)


def _parse_int(value: str) -> int:
    """문자열을 정수로 변환하고 실패 시 Redis 호환 예외를 발생시킨다.

    파이썬의 기본 예외를 그대로 노출하지 않는 이유는
    명령 계층이 사용자에게 일관된 에러 의미와 메시지를 제공해야 하기 때문이다.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        raise NotIntegerError()
