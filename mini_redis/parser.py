def tokenize(line: str) -> list[str]:
    """명령줄 한 줄을 공백과 큰따옴표 규칙에 따라 토큰 목록으로 분해한다.

    따옴표 밖에서는 연속된 공백을 구분자로 사용하고,
    따옴표 안에서는 공백도 데이터로 유지한다.
    큰따옴표를 만나면 quoted token을 시작하거나 끝내며,
    닫히지 않은 따옴표가 있어도 지금까지 모은 내용을 토큰으로 남겨
    입력 손실 없이 상위 계층이 후속 판단을 할 수 있게 한다.
    """
    tokens: list[str] = []
    current_chars: list[str] = []
    in_quotes = False
    i = 0
    length = len(line)

    while i < length:
        ch = line[i]

        if in_quotes:
            if ch == '"':
                tokens.append("".join(current_chars))
                current_chars = []
                in_quotes = False
            else:
                current_chars.append(ch)
            i += 1
            continue

        if ch.isspace():
            if current_chars:
                tokens.append("".join(current_chars))
                current_chars = []
            i += 1
            continue

        if ch == '"':
            if current_chars:
                tokens.append("".join(current_chars))
                current_chars = []
            in_quotes = True
            i += 1
            continue

        current_chars.append(ch)
        i += 1

    if current_chars:
        tokens.append("".join(current_chars))
    elif in_quotes:
        tokens.append("".join(current_chars))

    return tokens
