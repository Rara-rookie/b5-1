# Mini Redis 문서

## 개요

`mini_redis`는 CLI 기반의 작은 In-Memory Key-Value 저장소다. 해시맵, 이중 연결 리스트, 최소 힙을 직접 조합해 문자열 저장, TTL, LRU 기반 메모리 제거를 처리한다.

- 패키지: `mini_redis`
- 진입점: `mini_redis.__main__`
- 패키지 내부 import: 전부 상대 import 사용

실행:

- `python -m mini_redis`

프롬프트:

- `mini-redis>`

종료:

- `exit`
- `quit`

---

## 요구사항 분해

### 1) CLI와 명령 처리
구현된 명령은 다음과 같다.

- `SET key value`
- `GET key`
- `DEL key`
- `EXISTS key`
- `DBSIZE`
- `KEYS`
- `CONFIG SET maxmemory bytes`
- `INFO memory`
- `EXPIRE key seconds`
- `TTL key`

출력은 Redis 스타일 문자열을 따른다.

- 성공: `OK`
- 없음: `(nil)`
- 정수: `(integer) N`
- 오류: `(error) ...`

### 2) 값 파싱
입력 파서는 다음 두 형태를 지원한다.

- 공백 없는 값
- 큰따옴표로 감싼 값

예:

- `SET a hello`
- `SET user:1 "Alice"`

### 3) 저장 구조
내장 `dict`, `set`, `collections` 없이 다음 구조를 사용한다.

- 해시맵: 데이터 저장, TTL 맵, LRU 노드 맵
- 이중 연결 리스트: LRU 순서 관리
- 최소 힙: TTL 만료 시각 관리
- `list`: 버킷 배열과 힙 내부 배열 같은 인덱스 저장소로 사용

### 4) TTL 처리
- `EXPIRE key seconds`
- `TTL key`

설계 결정:

- `seconds <= 0` 이면 즉시 만료 처리
- TTL 남은 초는 `max(0, ceil(expire_at - now))`
- TTL 힙은 lazy deletion 전략 사용
- 키 기반 명령 전반에서 만료 키는 먼저 정리되어 없는 키처럼 처리됨

### 5) 메모리 관리와 LRU
- `CONFIG SET maxmemory bytes`
- `INFO memory`

설계 결정:

- `used_memory = Σ(len(utf8(key)) + len(utf8(value)))`
- 자료구조 오버헤드는 계산하지 않음
- `maxmemory > 0`에서 초과 시 LRU부터 제거
- 단일 엔트리 크기 자체가 `maxmemory`를 넘으면 저장하지 않고 OOM 에러

### 6) KEYS 출력
- 전체 키를 배열 비슷한 형식으로 출력
- 빈 경우 `'(empty array)'` 반환

---

## 모듈 계약과 설계 결정

## 패키지 구조

- `mini_redis/__main__.py`
- `mini_redis/cli.py`
- `mini_redis/commands.py`
- `mini_redis/errors.py`
- `mini_redis/hashmap.py`
- `mini_redis/heap.py`
- `mini_redis/linked_list.py`
- `mini_redis/parser.py`
- `mini_redis/store.py`

---

### `linked_list.py`
이중 연결 리스트와 노드를 제공한다.

#### 계약
- `Node`
  - 필드: `data`, `prev`, `next`
- `DoublyLinkedList`
  - `insert_front`
  - `insert_back`
  - `remove_front`
  - `remove_back`
  - `remove_node`
  - `move_to_front`
  - `is_empty`
  - `__iter__`

#### 설계 결정
- LRU 추적용 리스트로 사용
- 노드를 직접 들고 있어 `move_to_front`, `remove_node`를 O(1)로 수행

---

### `hashmap.py`
체이닝 방식 해시맵을 제공한다.

#### 계약
- `HashMap`
  - `_hash`
  - `put`
  - `get`
  - `remove`
  - `contains`
  - `keys`
  - `size`
  - `_resize`

#### 설계 결정
- 버킷은 `DoublyLinkedList` 배열
- 해시 함수는 djb2 형태
- 충돌은 버킷 연결 리스트로 해결
- 로드 팩터 `0.75` 초과 시 버킷 2배 확장

---

### `heap.py`
`(expire_at, key)`를 담는 최소 힙을 제공한다.

#### 계약
- `MinHeap`
  - `push`
  - `pop`
  - `peek`
  - `size`
  - `_heapify_up`
  - `_heapify_down`

#### 설계 결정
- TTL 만료 시각이 가장 빠른 항목을 빨리 찾기 위해 사용
- 배열 기반 구현
- lazy deletion은 `store.py`에서 현재 TTL 맵과 대조해 처리

---

### `errors.py`
CLI 표준 에러 메시지용 예외 계층을 제공한다.

#### 계약
- `RedisError`
- `UnknownCommandError`
- `WrongArgsError`
- `NotIntegerError`
- `OOMError`

#### 설계 결정
- 실행부에서 예외를 잡아 문자열 그대로 출력
- 에러 포맷을 예외 클래스에서 일관되게 생성

---

### `parser.py`
입력 라인을 토큰으로 분해한다.

#### 계약
- `tokenize(line: str) -> list[str]`

#### 설계 결정
- 공백 분리
- 큰따옴표 묶음 지원
- 빈 입력은 빈 리스트 반환

---

### `commands.py`
토큰을 명령으로 해석하고 결과 문자열을 만든다.

#### 계약
- `execute(store, tokens) -> str`

#### 설계 결정
- 명령별 인자 수 검증
- 정수 파싱 실패 시 `NotIntegerError`
- 모든 `RedisError`를 잡아 `(error) ...` 문자열 반환
- `KEYS`는 여러 줄 문자열로 반환
- `INFO memory`는 3줄 문자열 반환

---

### `store.py`
저장소 핵심 엔진이다.

#### 계약
- `MiniRedisStore`
  - `set`
  - `get`
  - `delete`
  - `exists`
  - `dbsize`
  - `keys`
  - `set_maxmemory`
  - `info_memory`
  - `expire`
  - `ttl`
  - `_is_expired`
  - `_evict_if_needed`

#### 설계 결정
- `_data`: 실제 key-value 저장
- `_ttl_map`: key -> expire_at 저장
- `_lru_nodes`: key -> LRU 리스트 노드 저장
- `_lru_list`: 최근 사용 순서 관리
- `_ttl_heap`: 가장 빠른 만료 후보 관리
- `now_fn` 주입 가능, 기본값은 `time.time`

#### 동작 요약
- `SET`
  - 만료 정리
  - 단일 엔트리 OOM 검사
  - 기존 값 덮어쓰기 시 기존 메모리 차감
  - 기존 TTL 제거
  - LRU를 앞으로 이동 또는 신규 삽입
  - 필요 시 LRU 제거
- `GET`
  - 만료면 삭제 후 `None`
  - 존재하면 LRU 갱신 후 값 반환
- `DEL`
  - 데이터, TTL, LRU 구조를 함께 정리
- `EXPIRE`
  - 없는 키면 `0`
  - `seconds <= 0`이면 즉시 삭제 후 `1`
  - 아니면 TTL 맵과 힙에 등록
- `TTL`
  - 없으면 `-2`
  - TTL 없으면 `-1`
  - 있으면 남은 초 반환
- `INFO memory`
  - `(used_memory, maxmemory, evicted_keys)` 반환

---

### `cli.py`
REPL 루프를 담당한다.

#### 계약
- `run() -> None`

#### 설계 결정
- 프롬프트: `mini-redis>`
- `EOFError` 처리
- `exit`, `quit` 종료
- 빈 입력 결과는 출력 생략

---

### `__main__.py`
모듈 실행 진입점이다.

#### 계약
- `main() -> None`

#### 설계 결정
- `cli.run()`만 호출

---

## 단계별 실행 계획

### 1단계: 패키지 뼈대 구성
- `mini_redis` 패키지 생성
- `__main__.py`, `cli.py` 작성
- 내부 import를 상대 import로 통일

### 2단계: 기초 자료구조 구현
- `linked_list.py` 구현
- `hashmap.py` 구현
- `heap.py` 구현

### 3단계: 에러 계층과 파서 구현
- `errors.py` 구현
- `parser.py`에서 공백/큰따옴표 토큰화 구현

### 4단계: 저장소 코어 구현
- `MiniRedisStore` 구성
- 데이터 저장, 메모리 계산
- LRU 리스트와 노드 맵 연결
- TTL 맵과 힙 연결
- lazy deletion purge 구현

### 5단계: 명령 실행기 구현
- `commands.py`에서 명령 라우팅
- 인자 수 검사
- 정수 파싱
- Redis 스타일 문자열 반환

### 6단계: CLI 통합
- `cli.run()`에서 입력-파싱-실행-출력 반복
- `exit`/`quit`/EOF 처리

### 7단계: 인수 시험 수행
- 기본 명령
- TTL
- 메모리 제한
- 오류 메시지
- REPL 진입점 실행 확인

---

## 인수 시험 목록과 각 시험이 확인하는 것

### 1. `SET/GET` 기본 저장 조회
입력:
- `SET user:1 "Alice"`
- `GET user:1`

확인:
- `SET` 성공 시 `OK`
- `GET`이 `"Alice"` 반환
- 큰따옴표 값 파싱 정상

실행 결과:
- `(ok) -> "Alice"`

---

### 2. `DEL/EXISTS/DBSIZE` 기본 삭제 흐름
입력:
- `SET a hello`
- `DBSIZE`
- `EXISTS a`
- `DEL a`
- `EXISTS a`

확인:
- 저장 후 개수 증가
- 존재 여부 확인 가능
- 삭제 후 존재하지 않음

실행 결과에 포함:
- `(ok) -> (integer) 0`

---

### 3. LRU 제거 후 `GET` 결과
입력:
- `CONFIG SET maxmemory 30`
- `SET user:1 "Alice"`
- `SET user:2 "Bob"`
- `SET user:3 "Charlie"`
- `GET user:1`

확인:
- 메모리 초과 시 LRU 제거 수행
- 제거된 키 조회 시 `(nil)`

실행 결과:
- `(ok) -> (nil)`

---

### 4. `INFO memory` used_memory 확인
입력:
- 메모리 제한 설정 후 여러 키 저장
- `INFO memory`

확인:
- `used_memory`가 구현 공식대로 계산됨

실행 결과:
- `(ok) -> used_memory:22`

---

### 5. `INFO memory` evicted_keys 확인
입력:
- LRU 제거가 발생한 뒤 `INFO memory`

확인:
- 제거된 키 수 누적 카운트

실행 결과:
- `(ok) -> evicted_keys:1`

---

### 6. `EXPIRE/TTL` 정상 TTL 반환
입력:
- `SET k v`
- `EXPIRE k 100`
- `TTL k`

확인:
- TTL 설정 성공
- 남은 TTL 정수 반환

실행 결과:
- `(ok) -> (integer) 100`

---

### 7. `TTL` 없는 키 처리
입력:
- `TTL nope`

확인:
- 없는 키는 `-2`

실행 결과:
- `(ok) -> (integer) -2`

---

### 8. `TTL`은 없지만 키는 존재하는 경우
입력:
- `SET k v`
- `TTL k`

확인:
- TTL 미설정 키는 `-1`

실행 결과:
- `(ok) -> (integer) -1`

---

### 9. 인자 개수 오류
입력:
- `GET`

확인:
- 인자 부족 시 표준 오류 메시지 출력

실행 결과:
- `(ok) -> wrong number of arguments`

---

### 10. 정수 파싱 오류
입력:
- `CONFIG SET maxmemory abc`

확인:
- 정수 파싱 실패 시 표준 오류 메시지 출력

실행 결과:
- `(ok) -> value is not an integer`

---

### 11. 알 수 없는 명령
입력:
- `HELLO`

확인:
- 미지원 명령에 대해 unknown command 오류 출력

실행 결과:
- `(error) ERR unknown command 'HELLO'`

---

### 12. 컴파일 가능성
확인:
- `py_compile` 통과

의미:
- 문법 오류 없이 패키지가 로드 가능

---

## 위험 요소와 대응

### 1) TTL 힙에 stale 항목이 쌓이는 문제
위험:
- 같은 키에 `EXPIRE`를 여러 번 하면 힙에 이전 만료 정보가 남음

대응:
- lazy deletion 사용
- `pop` 시 `_ttl_map`의 현재 `expire_at`과 비교해 유효성 재검증

---

### 2) LRU 제거와 메모리 계산 불일치
위험:
- 삭제 시 `_used_memory`가 정확히 갱신되지 않으면 `INFO memory`와 제거 조건이 틀어짐

대응:
- `_delete_key_internal`에서 메모리 차감과 구조 정리를 한곳에서 처리
- `_evict_if_needed`에서도 제거 직전 값 크기만큼 차감

---

### 3) 덮어쓰기 시 TTL이 남는 문제
위험:
- `SET`으로 기존 키를 갱신했는데 이전 TTL이 유지되면 요구사항 위반

대응:
- `set()`에서 기존 TTL 맵 엔트리를 명시적으로 제거

---

### 4) 만료 키가 조회/삭제 전에 남아 있는 문제
위험:
- 만료 키가 `GET`, `EXISTS`, `TTL`, `DBSIZE`, `KEYS`, `INFO` 결과를 오염시킬 수 있음

대응:
- `_purge_expired()`를 주요 경로에서 호출
- `_is_expired()`가 만료 시 즉시 내부 삭제 수행

---

### 5) 단일 엔트리 OOM 처리 누락
위험:
- 어떤 키 하나가 `maxmemory`보다 큰데도 저장을 시도하면 요구사항 위반

대응:
- `set()` 초입에서 새 엔트리 크기를 먼저 검사하고 `OOMError` 발생

---

### 6) LRU 노드와 실제 데이터 불일치
위험:
- 데이터 삭제 후 LRU 노드가 남으면 제거 순서가 깨질 수 있음

대응:
- `_delete_key_internal()`에서 `_data`, `_ttl_map`, `_lru_list`, `_lru_nodes`를 함께 정리

---

### 7) 잘못된 입력 파싱
위험:
- 큰따옴표 값을 제대로 나누지 못하면 `SET` 인자 수가 틀어짐

대응:
- `parser.tokenize()`가 공백/큰따옴표 규칙을 직접 처리
- 빈 입력은 빈 토큰으로 반환해 안전하게 무시

---

## 실제 실행 확인 요약

실제 제공된 실행 결과로 확인된 항목:

- `py_compile` 통과
- `python -m mini_redis` 진입 가능
- `SET/GET` 정상
- `DBSIZE/EXISTS/DEL` 정상
- `CONFIG SET maxmemory` 정상
- LRU 제거 후 `GET`이 `(nil)`
- `INFO memory`에서 `used_memory:22`, `maxmemory:30`, `evicted_keys:1`
- `EXPIRE/TTL` 정상
- 없는 키 `TTL`이 `-2`
- TTL 없는 키 `TTL`이 `-1`
- 인자 개수 오류 메시지 정상
- 정수 파싱 오류 메시지 정상
- unknown command 오류 메시지 정상

---

## 구현 범위 요약

구현됨:
- 문자열 키-값 저장
- TTL
- LRU 메모리 제거
- 메모리 사용량 조회
- CLI REPL
- 큰따옴표 값 파싱
- 상대 import 기반 패키지 실행

구현되지 않음:
- 네트워크 통신
- 파일 영속성
- Redis의 List/Set/Sorted Set
- 패턴 매칭 KEYS
- 동시성 처리
- 보너스 과제 기능들
