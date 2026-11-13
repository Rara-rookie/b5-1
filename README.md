# Mini Redis

CLI 기반의 작은 In-Memory Key-Value 저장소입니다.  
해시맵, 이중 연결 리스트, 최소 힙을 직접 구현해 문자열 저장, TTL, LRU 기반 메모리 제거를 지원합니다.

## 실행 방법

Python 3.8 이상에서 패키지 모드로 실행합니다.

```bash
python -m mini_redis
```

실행 후 프롬프트가 표시됩니다.

```text
mini-redis>
```

종료 명령:

- `exit`
- `quit`

EOF 입력도 종료 처리합니다.

## 패키지 구조

진입점:

- `mini_redis.__main__`

패키지 내부 import:

- 모두 상대 import 사용

주요 모듈:

- `linked_list.py` — 이중 연결 리스트
- `hashmap.py` — 체이닝 방식 해시맵
- `heap.py` — TTL용 최소 힙
- `store.py` — KV 저장소, LRU, TTL, 메모리 관리
- `parser.py` — 입력 토큰화
- `commands.py` — 명령 실행 및 출력 문자열 생성
- `cli.py` — REPL
- `errors.py` — CLI 에러 메시지 예외

## 저장 방식

이 프로그램은 메모리 내에서만 동작합니다.

- 저장 파일 위치: 없음
- 저장 파일 형식: 없음
- 데이터 영속성: 지원하지 않음

즉, 프로그램 종료 후 데이터는 유지되지 않습니다.

## 지원 명령

### 문자열 명령

- `SET key value`
- `GET key`
- `DEL key`
- `EXISTS key`
- `DBSIZE`
- `KEYS`

### 메모리 명령

- `CONFIG SET maxmemory bytes`
- `INFO memory`

### TTL 명령

- `EXPIRE key seconds`
- `TTL key`

## 값 입력 규칙

다음 두 형태를 지원합니다.

- 공백 없는 값
- 큰따옴표로 감싼 값

예:

```text
SET a hello
SET user:1 "Alice"
```

## 동작 규칙

- `used_memory = Σ(len(utf8(key)) + len(utf8(value)))`
- 자료구조 오버헤드는 메모리 계산에서 제외
- `SET` 성공 시 LRU 갱신
- `GET` 성공 시에만 LRU 갱신
- 기존 키를 `SET`으로 덮어쓰면 기존 TTL은 제거
- `seconds <= 0`인 `EXPIRE`는 즉시 만료 처리
- `TTL`은 `max(0, ceil(expire_at - now))` 정수 반환
- TTL 힙은 lazy deletion 전략 사용
- `KEYS` 결과가 비어 있으면 `(empty array)` 반환
- `maxmemory > 0`일 때 초과하면 LRU 키부터 제거
- 단일 엔트리 자체가 `maxmemory`보다 크면 저장하지 않고 OOM 에러 반환

## 주요 명령 예시

### 기본 저장/조회

```text
mini-redis> SET user:1 "Alice"
OK
mini-redis> GET user:1
"Alice"
```

### 존재 확인/삭제

```text
mini-redis> SET a hello
OK
mini-redis> EXISTS a
(integer) 1
mini-redis> DEL a
(integer) 1
mini-redis> EXISTS a
(integer) 0
```

### 키 개수 조회

```text
mini-redis> DBSIZE
(integer) 1
```

### 메모리 제한 설정과 확인

```text
mini-redis> CONFIG SET maxmemory 30
OK
mini-redis> INFO memory
used_memory:22
maxmemory:30
evicted_keys:1
```

### TTL 설정과 조회

```text
mini-redis> SET k v
OK
mini-redis> EXPIRE k 100
(integer) 1
mini-redis> TTL k
(integer) 100
```

TTL이 없는 키:

```text
mini-redis> SET k v
OK
mini-redis> TTL k
(integer) -1
```

없는 키:

```text
mini-redis> TTL nope
(integer) -2
```

### LRU 제거 예시

```text
mini-redis> CONFIG SET maxmemory 30
OK
mini-redis> SET user:1 "Alice"
OK
mini-redis> SET user:2 "Bob"
OK
mini-redis> SET user:3 "Charlie"
OK
mini-redis> GET user:1
(nil)
```

실행 결과 기준으로 메모리 정보는 다음처럼 출력됩니다.

```text
used_memory:22
maxmemory:30
evicted_keys:1
```

## 출력 형식

성공/조회 결과 예:

- `OK`
- `"Alice"`
- `(nil)`
- `(integer) 1`
- `(integer) 0`

배열 출력 예:

```text
1. "user:2"
2. "user:3"
```

빈 키 목록:

```text
(empty array)
```

## 에러 출력

잘못된 명령:

```text
(error) ERR unknown command 'HELLO'
```

인자 개수 오류:

```text
(error) ERR wrong number of arguments for 'GET' command
```

정수 파싱 실패:

```text
(error) ERR value is not an integer or out of range
```

메모리 초과:

```text
(error) OOM command not allowed when used_memory > 'maxmemory'
```

## 자료구조 구현 요약

### DoublyLinkedList

노드 필드:

- `prev`
- `next`
- `data`

주요 메서드:

- `insert_front`
- `insert_back`
- `remove_front`
- `remove_back`
- `remove_node`
- `move_to_front`
- `is_empty`

### HashMap

체이닝 방식으로 구현되어 있습니다.

주요 메서드:

- `put`
- `get`
- `remove`
- `contains`
- `keys`
- `size`

특징:

- 해시 함수 직접 구현
- 로드 팩터 0.75 초과 시 버킷 2배 확장

### MinHeap

`(expire_at, key)` 튜플을 저장하는 최소 힙입니다.

주요 메서드:

- `push`
- `pop`
- `peek`
- `size`

내부 정리:

- `_heapify_up`
- `_heapify_down`

## 설계 고찰

다음 세 가지는 현재 구현이 더 큰 규모와 다른 정책에서 어떻게 달라져야 하는지에 대한 고찰이다. 상세 분석은 note.md의 Q12~Q14에 있다.

### LFU로 전환한다면

현재 LRU 구현은 `_lru_nodes`(key → 노드 해시맵)와 `_lru_list`(DoublyLinkedList) 한 개로 최근 사용 순서를 관리한다. LFU(Least Frequently Used)는 사용 빈도를 기준으로 제거해야 하므로 자료구조가 달라진다.

#### LFU 핵심 구성요소

| 구성요소 | LRU 현재 | LFU 전환 후 |
|---------|---------|-----------|
| 메인 저장소 | `_data`: `key → value` | `key → (value, freq, node)` |
| 순서 관리 | `_lru_nodes`: `key → LRU 노드` + `_lru_list`: 단일 이중연결리스트 | `_freq_lists`: `freq → DoublyLinkedList` (빈도별 버킷) |
| 추적 정보 | 없음 | `_min_freq`: 현재 최소 빈도 |

#### 동작 변화

- **GET/SET**: 노드를 현재 freq 버킷에서 제거한 뒤 freq+1 버킷으로 이동. `_min_freq` 갱신. 모두 O(1).
- **제거 대상**: `_lru_list`의 뒤쪽이 아니라, `_freq_lists[_min_freq]` 버킷의 뒤쪽(같은 빈도 내 가장 오래된 항목).

코드 변경 위치: `store.py`의 `_lru_nodes`, `_lru_list` 제거 후 `_freq_lists`, `_min_freq` 추가. 축출 루프 재구성.


### 데이터가 10만 건으로 늘어나면

현재 구조는 과제 범위에서는 충분하지만, 규모 확장 시 몇 가지 지점이 병목이 된다.

| 병목 | 원인 | 개선안 |
|-----|------|-------|
| `HashMap._resize` 일괄 재해싱 | 로드팩터 초과 순간 모든 엔트리를 새 배열로 한 번에 옮김. O(N) 일괄 정지. | **Incremental rehashing**: `old_table`, `new_table`, `rehash_idx`를 유지하고, 각 명령마다 버킷 몇 개씩만 옮김. 지연시간 분산. |
| `KEYS` 전체 버킷 순회 | 모든 키를 반환하려면 전체 저장소를 훑어야 함. O(N). | **SCAN 커서**: 일부씩 반환하고 클라이언트가 반복 조회. 응답 시간 일정 유지. |
| TTL MinHeap의 stale 튜플 누적 | 같은 키가 여러 번 EXPIRE 될 때마다 힙에 중복 항목 축적. 큰 힙은 조회 느림. | **Indexed min-heap** 또는 **주기적 active expire 샘플링**: 주기적으로 샘플(예: 100개 항목) 만료 여부 검사해 정산. |
| 단일 스레드 단일 저장소 병목 | 이 구현은 스레드 세이프하지 않으며 쓰기 락이 없으므로, 고도의 동시성은 구조상 불가능. | **키 해시로 샤드 분할**: `hash(key) % shard_count`로 N개 저장소에 분산 저장. 샤드별 락 또는 멀티프로세스. |


### used_memory에 자료구조 오버헤드를 포함한다면

현재 공식은 `Σ(len(utf8(key)) + len(utf8(value)))`이며, 노드·포인터·버킷·힙 원소는 제외한다(과제 명세).

#### 포함했을 때의 변화

- **작은 항목 조기 축출**: 오버헤드가 상당하면 적은 바이트 데이터도 빠르게 메모리 한계에 닿음.
- **0에 도달 불가**: 모든 키를 삭제해도 버킷 배열과 stale 힙 튜플이 남음.
- **리사이즈 순간 메모리 피크**: 기존 배열과 새 배열이 동시 존재.

#### 공정한 비교를 위한 보정

1. `sys.getsizeof()` 대신 고정 상수로 계산: `ENTRY_OVERHEAD`, `LRU_NODE_OVERHEAD`, `TTL_ENTRY_OVERHEAD`, `HEAP_TUPLE_OVERHEAD`
2. 버킷 배열 크기와 stale 힙 튜플 정산 규칙 명시
3. eviction 시점 허용 오차 설정(1~2개 엔트리)

이 과제는 채점 재현성을 위해 오버헤드 제외 공식을 유지한다.

## import/export CSV 스키마

지원하지 않습니다.

- CSV import: 없음
- CSV export: 없음
- CSV 스키마: 없음
