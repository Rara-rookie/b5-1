# Mini Redis 문서

작은 CLI 기반 Redis 스타일 Key-Value 저장소 구현이다.  
패키지 이름은 `mini_redis`, 실행 진입점은 `mini_redis.__main__`이다.

구현된 기능은 다음과 같다.

- String 명령어
  - `SET`
  - `GET`
  - `DEL`
  - `EXISTS`
  - `DBSIZE`
  - `KEYS`
- 메모리 관리
  - `CONFIG SET maxmemory`
  - `INFO memory`
- TTL 관리
  - `EXPIRE`
  - `TTL`
- REPL CLI
  - 프롬프트: `mini-redis>`
  - 종료: `exit`, `quit`

## 파일 구조와 근거

- `mini_redis/__main__.py`
  - `main()`에서 `cli.run()` 호출
- `mini_redis/cli.py`
  - REPL 루프, 프롬프트 출력, `exit`/`quit` 처리
- `mini_redis/parser.py`
  - 입력 문자열 토큰화
  - 큰따옴표 값과 공백 없는 값 지원
- `mini_redis/commands.py`
  - 명령어 분기, 인자 수 검사, Redis 스타일 출력 문자열 생성
- `mini_redis/errors.py`
  - 표준 에러 메시지 예외 계층
- `mini_redis/linked_list.py`
  - `Node(prev, next, data)` 기반 이중 연결 리스트
- `mini_redis/hashmap.py`
  - 체이닝 방식 해시맵
- `mini_redis/heap.py`
  - `(expire_at, key)` 최소 힙
- `mini_redis/store.py`
  - 해시맵 + LRU 리스트 + TTL 힙을 조합한 저장소 엔진

패키지 내부 import는 모두 상대 import를 사용한다.  
예: `from .cli import run`, `from .store import MiniRedisStore`

---

## 이 과제로 배우는 개념의 원리와 이유

### 1. 해시맵이 빠른 이유
해시맵은 키를 해시 함수로 정수 인덱스로 바꿔 버킷에 접근한다.  
평균적으로 `put/get/remove`를 O(1)에 가깝게 수행할 수 있다.

이 구현에서는 충돌을 피할 수 없기 때문에 체이닝을 사용한다.  
같은 버킷으로 들어온 항목들을 연결 리스트로 저장해 충돌을 처리한다.

왜 체이닝을 쓰는가:
- 충돌이 나도 저장 가능하다
- 버킷 배열을 고정 길이 인덱스 저장소로 두고, 각 칸에서 연결 리스트로 여러 항목을 담을 수 있다

### 2. 이중 연결 리스트가 LRU에 적합한 이유
LRU는 “최근 사용됨 / 오래 사용되지 않음”의 순서를 유지해야 한다.  
이중 연결 리스트는 노드를 알고 있을 때 삭제와 이동을 O(1)로 할 수 있다.

왜 단일 연결 리스트보다 이중 연결 리스트인가:
- 임의 노드 제거 시 `prev`가 있어야 O(1)로 끊기 쉽다
- 최근 사용된 키를 맨 앞으로, 가장 오래된 키를 맨 뒤로 두기 좋다

### 3. 해시맵 + 이중 연결 리스트 조합으로 O(1) LRU가 되는 이유
LRU만 연결 리스트로 관리하면 특정 키를 찾는 데 O(n)이 든다.  
반대로 해시맵만 있으면 사용 순서를 바로 갱신하기 어렵다.

그래서:
- 해시맵은 `key -> LRU 리스트 노드`
- 이중 연결 리스트는 실제 사용 순서

이 조합으로:
- `GET` 성공 시 해당 노드를 즉시 찾아 맨 앞으로 이동
- `SET` 성공 시 새 키는 맨 앞으로 추가, 기존 키는 앞으로 이동
- 메모리 초과 시 리스트 뒤쪽에서 가장 오래된 키 제거

### 4. 최소 힙이 TTL에 적합한 이유
TTL은 “가장 빨리 만료될 키”를 빠르게 찾아야 한다.  
최소 힙의 루트는 항상 가장 작은 값이므로, `(expire_at, key)`를 넣으면 가장 빠른 만료 시각이 맨 위에 온다.

왜 힙을 쓰는가:
- 다음 만료 대상을 빠르게 확인 가능
- `peek()`로 가장 빠른 만료 후보 확인
- 만료 시 `pop()`하며 정리

### 5. lazy deletion이 필요한 이유
TTL을 다시 설정하면 같은 키가 힙에 여러 번 들어갈 수 있다.  
힙 내부 임의 위치의 오래된 항목을 직접 지우는 대신, 꺼낼 때 현재 TTL 맵 값과 비교해 유효성만 재검증한다.

장점:
- 구현이 단순하다
- 힙 연산 구조를 깨지 않는다

### 6. 메모리 제한과 LRU 제거 원리
이 구현의 메모리 사용량은 자료구조 오버헤드를 제외하고 문자열 바이트 길이만 센다.

공식:
- `used_memory = Σ(len(utf8(key)) + len(utf8(value)))`

왜 이렇게 계산하는가:
- 과제 요구사항의 산정 기준을 그대로 반영
- 키/값 저장량 변화가 메모리에 어떻게 영향을 주는지 명확히 추적 가능

메모리 초과 처리 원리:
1. `SET` 전에 단일 엔트리 크기가 `maxmemory`보다 큰지 검사
2. 초과면 저장하지 않고 OOM
3. 저장 후 전체 `used_memory`가 `maxmemory`를 넘으면
4. LRU 리스트 뒤에서부터 키를 제거
5. `used_memory <= maxmemory`가 될 때까지 반복
6. 제거 횟수는 `evicted_keys`에 누적

---

## 구현이 그 개념을 어디서 어떻게 쓰는지

### 이중 연결 리스트 사용 위치
근거 파일: `mini_redis/linked_list.py`, `mini_redis/store.py`

- `Node`는 `data`, `prev`, `next` 필드를 가짐
- `DoublyLinkedList`는
  - `insert_front`
  - `insert_back`
  - `remove_front`
  - `remove_back`
  - `remove_node`
  - `move_to_front`
  - `is_empty`
  - `__iter__`
  를 제공한다

`store.py`에서 LRU 관리에 사용:
- `self._lru_list: DoublyLinkedList`
- 새 키 저장 시 `insert_front(key)`
- `GET` 성공 시 `move_to_front(node)`
- 메모리 초과 시 `remove_back()`으로 LRU 키 추출

### 해시맵 사용 위치
근거 파일: `mini_redis/hashmap.py`, `mini_redis/store.py`

`HashMap`은 다음 저장소로 쓰인다.

- `self._data`
  - 실제 `key -> value`
- `self._ttl_map`
  - `key -> expire_at`
- `self._lru_nodes`
  - `key -> LRU 연결 리스트 노드`

충돌 해결:
- 버킷별 `DoublyLinkedList` 사용
- 각 노드 `data`는 `(key, value)` 튜플

해시 함수:
- `hashmap.py`의 `_hash`
- `5381` 시작값과 문자 누적 방식 사용

리사이즈:
- 로드 팩터가 `0.75` 초과 시 `_resize()`
- 버킷 2배 확장 후 재삽입

### 최소 힙 사용 위치
근거 파일: `mini_redis/heap.py`, `mini_redis/store.py`

- `self._ttl_heap: MinHeap`
- `EXPIRE` 시 `(expire_at, key)`를 `push`
- `_purge_expired()`에서
  - `peek()`로 가장 빠른 만료 후보 확인
  - 현재 시각보다 작거나 같으면 `pop()`
  - `ttl_map`의 현재 값과 비교해 유효한 항목만 삭제

### 파서 사용 위치
근거 파일: `mini_redis/parser.py`

지원 규칙:
- 공백 없는 값 지원
- 큰따옴표로 감싼 값 지원

예:
- `SET a hello`
- `SET user:1 "Alice"`

### 명령 실행과 출력 형식
근거 파일: `mini_redis/commands.py`, `mini_redis/errors.py`

출력 형식:
- 성공: `OK`
- 값 없음: `(nil)`
- 정수: `(integer) N`
- 빈 KEYS: `(empty array)`
- 오류: `(error) ...`

구현된 명령어:
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

### TTL 관련 결정 사항
근거 파일: `mini_redis/store.py`

- `seconds <= 0`인 `EXPIRE`는 즉시 만료 처리
  - 존재하면 삭제 후 `(integer) 1`
- `TTL` 남은 시간은
  - `max(0, ceil(expire_at - now))`
- 기존 키를 `SET`으로 덮어쓰면 TTL 제거
  - `self._ttl_map.remove(key)`

### 메모리 계산 방식
근거 파일: `mini_redis/store.py`

- `_entry_size(key, value)`
  - `len(key.encode("utf-8")) + len(value.encode("utf-8"))`

자료구조 오버헤드는 포함하지 않는다.

---

## 명령어 동작 요약

### `SET key value`
- 저장 성공 시 `OK`
- 기존 키면 값 덮어쓰기
- 기존 TTL은 제거
- LRU 최신으로 갱신
- 메모리 초과 시 LRU 제거 수행
- 단일 엔트리가 `maxmemory`보다 크면 OOM

### `GET key`
- 만료되었으면 먼저 삭제 후 `(nil)`
- 없으면 `(nil)`
- 있으면 `"value"`
- 성공한 경우만 LRU 갱신

### `DEL key`
- 있으면 `(integer) 1`
- 없으면 `(integer) 0`
- 데이터/TTL/LRU에서 함께 제거

### `EXISTS key`
- 존재하면 `(integer) 1`
- 없거나 만료면 `(integer) 0`

### `DBSIZE`
- 만료 정리 후 현재 키 수 반환

### `KEYS`
- 만료 정리 후 전체 키 목록 반환
- 비어 있으면 `(empty array)`

### `CONFIG SET maxmemory bytes`
- `0`은 무제한
- 음수나 정수 파싱 실패는 에러
- 설정 후 즉시 만료 정리 및 필요 시 제거 수행

### `INFO memory`
- `used_memory`
- `maxmemory`
- `evicted_keys`

### `EXPIRE key seconds`
- 없으면 `(integer) 0`
- `seconds <= 0`이면 즉시 삭제 후 `(integer) 1`
- 정상 설정 시 `(integer) 1`

### `TTL key`
- 없으면 `(integer) -2`
- TTL 없으면 `(integer) -1`
- 있으면 남은 초 `(integer) N`

---

## 실제 실행 출력 근거

### 기본 저장/조회
실행:
- `mini_redis.__main__`
- stdin:
  - `SET user:1 "Alice"`
  - `GET user:1`
  - `exit`

출력:
- `mini-redis> OK`
- `mini-redis> "Alice"`
- `mini-redis>`

### 삭제/존재/개수
실행:
- stdin:
  - `SET a hello`
  - `DBSIZE`
  - `EXISTS a`
  - `DEL a`
  - `EXISTS a`
  - `exit`

출력:
- `mini-redis> OK`
- `mini-redis> (integer) 1`
- `mini-redis> (integer) 1`
- `mini-redis> (integer) 1`
- `mini-redis> (integer) 0`
- `mini-redis>`

### LRU 제거 확인
실행:
- stdin:
  - `CONFIG SET maxmemory 30`
  - `SET user:1 "Alice"`
  - `SET user:2 "Bo`
  - 이후 추가 `SET`과 `GET user:1`

출력 일부:
- `mini-redis> OK`
- `mini-redis> OK`
- `mini-redis> OK`
- `mini-redis> OK`
- `mini-redis> (nil)`
- `mini-redis>`

이 출력은 메모리 초과 후 오래된 키가 제거되어 `GET user:1`이 `(nil)`이 됨을 보여준다.

### 메모리 정보
실행 출력:
- `mini-redis> used_memory:22`
- `maxmemory:30`
- `evicted_keys:1`
- `mini-redis>`

### TTL 설정/조회
실행:
- stdin:
  - `SET k v`
  - `EXPIRE k 100`
  - `TTL k`
  - `exit`

출력:
- `mini-redis> OK`
- `mini-redis> (integer) 1`
- `mini-redis> (integer) 100`
- `mini-redis>`

### TTL 없는 키
실행:
- stdin:
  - `SET k v`
  - `TTL k`
  - `exit`

출력:
- `mini-redis> OK`
- `mini-redis> (integer) -1`
- `mini-redis>`

### 없는 키 TTL
실행:
- stdin:
  - `TTL nope`
  - `exit`

출력:
- `mini-redis> (integer) -2`
- `mini-redis>`

### 에러 처리
실행:
- stdin:
  - `GET`
  - `exit`

출력:
- `mini-redis> (error) ERR wrong number of arguments for 'GET' command`
- `mini-redis>`

실행:
- stdin:
  - `HELLO`
  - `CONFIG SET maxmemory abc`
  - `exit`

출력:
- `mini-redis> (error) ERR unknown command 'HELLO'`
- `mini-redis> (error) ERR value is not an integer or out of range`
- `mini-redis>`

### 컴파일 확인
- `[통과] py_compile`

---

## 평가자가 물을 만한 질문과 답

### Q1. 왜 `dict` 대신 직접 해시맵을 구현했나?
A. 과제 요구사항이 내장 Key-Value 컬렉션 대체를 금지했고, 해시 함수·충돌 해결·리사이즈 원리를 직접 구현해 이해하는 것이 목표이기 때문이다. 근거는 `mini_redis/hashmap.py`다.

### Q2. 충돌은 어떻게 해결하나?
A. 체이닝 방식이다. 각 버킷은 `DoublyLinkedList`이고, 같은 인덱스로 해시된 `(key, value)`들을 연결 리스트에 저장한다. 근거는 `mini_redis/hashmap.py`의 `_buckets`와 순회 로직이다.

### Q3. 해시맵의 리사이즈는 언제 일어나나?
A. `self._size / self._capacity > 0.75`일 때 `_resize()`를 호출해 버킷 수를 2배로 늘린다. 근거는 `mini_redis/hashmap.py`.

### Q4. LRU를 O(1)로 갱신할 수 있는 이유는?
A. `key -> node`를 `self._lru_nodes` 해시맵에 저장하기 때문이다. 그래서 `GET`이나 `SET` 시 해당 노드를 바로 찾고 `move_to_front()` 할 수 있다. 근거는 `mini_redis/store.py`.

### Q5. 가장 오래된 키는 어떻게 찾나?
A. LRU 연결 리스트의 뒤(`tail`)가 가장 오래 사용되지 않은 키다. 메모리 초과 시 `remove_back()`으로 꺼낸다. 근거는 `mini_redis/store.py`의 `_evict_if_needed()`.

### Q6. TTL은 왜 힙으로 관리하나?
A. 가장 빠른 만료 키를 빨리 찾기 위해서다. 최소 힙의 루트가 최소 `expire_at`이므로 만료 정리에 적합하다. 근거는 `mini_redis/heap.py`와 `mini_redis/store.py`.

### Q7. TTL 힙에서 같은 키가 여러 번 들어갈 수 있는데 문제없나?
A. 문제없다. lazy deletion을 사용한다. 힙에서 꺼낸 `(expire_at, key)`가 현재 `ttl_map` 값과 다르면 무시한다. 근거는 `mini_redis/store.py`의 `_purge_expired()`.

### Q8. `SET`이 기존 키를 덮어쓸 때 TTL은 어떻게 되나?
A. TTL을 제거한다. `self._ttl_map.contains(key)`면 `remove(key)` 한다. 근거는 `mini_redis/store.py`의 `set()`.

### Q9. `GET`에서 만료된 키는 왜 LRU 갱신을 하지 않나?
A. 요구사항대로 만료 여부를 먼저 확인하고, 만료된 키는 삭제 후 없는 키처럼 처리하기 때문이다. 구현에서도 `_is_expired()`가 먼저 호출되고 만료면 `None`을 반환한다. 근거는 `mini_redis/store.py`의 `get()`.

### Q10. 메모리 사용량은 무엇을 기준으로 계산하나?
A. `len(utf8(key)) + len(utf8(value))`의 총합이다. 노드, 포인터, 버킷 같은 오버헤드는 제외한다. 근거는 `mini_redis/store.py`의 `_entry_size()`.

### Q11. 단일 값이 `maxmemory`보다 크면 어떻게 되나?
A. 저장하지 않고 `OOMError`를 발생시킨다. 근거는 `mini_redis/store.py`

### Q12. 만약 LRU 대신 LFU 정책을 구현한다면 자료구조를 어떻게 변경해야 하는가? (평가표 항목 4-1)

현재 구현은 `해시맵 + 이중 연결 리스트`로 **가장 최근에 사용된 항목을 앞쪽으로 이동**시키는 LRU 방식이다.  
반면 LFU(Least Frequently Used)는 **가장 적게 사용된 빈도(freq)** 를 기준으로 제거해야 하므로, 단순히 최근 사용 순서만 저장하는 리스트 하나로는 부족하다.

O(1)에 가까운 LFU를 구현하려면 보통 다음 3가지 핵심 구조가 필요하다.

#### 1) `key -> (value, freq, node)` 해시맵
각 key에 대해 다음 정보를 저장한다.

- `value`: 실제 값
- `freq`: 현재 접근 빈도
- `node`: 그 key가 속한 "빈도별 리스트" 내부 노드 참조

즉, 키를 해시로 즉시 찾고,
그 키가 현재 몇 번 사용되었는지와
어느 리스트 노드에 들어 있는지까지 바로 접근할 수 있어야 한다.

예시 개념:
- `"a" -> ("hello", 3, nodeA)`
- `"b" -> ("world", 1, nodeB)`

이 구조가 있어야 `GET a` 시
1. 값 조회
2. 현재 빈도 확인
3. 기존 리스트에서 O(1) 제거
4. 다음 빈도 리스트로 O(1) 이동  
을 수행할 수 있다.

#### 2) `freq -> DoublyLinkedList` 빈도 버킷 해시맵
빈도별로 이중 연결 리스트를 하나씩 둔다.

예를 들어:
- `freq=1` 리스트: 최근 들어온 저빈도 키들
- `freq=2` 리스트
- `freq=3` 리스트 ...

각 리스트 노드는 해당 빈도의 key를 담는다.

이 구조가 필요한 이유는 LFU에서 제거 대상이
1. **가장 작은 빈도**를 가져야 하고
2. 같은 빈도 안에서는 보통 **오래된 것부터 제거**해야 하기 때문이다.

즉 LFU는 실제로는 다음 정책이 된다.

- 1차 기준: **최소 사용 빈도**
- 2차 기준: **같은 빈도 내에서는 LRU**

따라서 각 빈도 버킷 내부는 이중 연결 리스트로 관리하면,
- 노드 제거 O(1)
- 앞/뒤 삽입 O(1)
- 같은 빈도 내 LRU tie-break 처리 O(1)

이 가능하다.

#### 3) `min_freq` 추적 변수
현재 저장된 모든 키 중 **최소 빈도값**을 별도 변수로 유지한다.

예:
- 현재 `min_freq = 1`

그러면 eviction이 필요할 때 전체 빈도 버킷을 스캔할 필요 없이,
즉시 `freq=1` 리스트에서 제거 대상을 꺼낼 수 있다.

이 변수가 없으면 "현재 최소 빈도가 몇인지"를 찾기 위해
여러 빈도 버킷을 순회해야 하므로 O(1) 보장이 깨진다.

---

### LFU에서 GET 동작 절차

`GET key`의 핵심은 **값 반환 + 사용 빈도 증가**이다.

1. 해시맵에서 `key`를 조회한다.
   - 없으면 nil/None 반환
   - 있으면 `(value, freq, node)`를 얻는다

2. 현재 빈도 버킷 `freq`의 리스트에서 해당 `node`를 제거한다.
   - 이중 연결 리스트이므로 O(1)

3. 만약 그 리스트가 비었고, `min_freq == freq`였다면
   - `min_freq`를 `freq + 1`로 올린다

4. `freq + 1` 버킷 리스트에 새 노드로 삽입한다
   - 보통 앞쪽에 삽입하여 "같은 빈도 내 최근 사용"을 표시

5. `key -> (value, freq+1, new_node)` 또는 node 참조를 갱신한다

6. `value`를 반환한다

즉 GET은 단순 조회가 아니라
**빈도 증가에 따른 버킷 이동 연산**까지 포함된다.

---

### LFU에서 SET 동작 절차

#### (1) 기존 key 갱신인 경우
이미 key가 존재한다면 다음 순서로 처리한다.

1. 해시맵에서 기존 엔트리 조회
2. value를 새 값으로 갱신
3. 보통 GET과 동일하게 freq를 1 증가시킨다  
   - 많은 LFU 구현은 write도 사용으로 간주
   - 과제 정책에 따라 "갱신은 빈도 증가 없음"으로 정할 수도 있으나, 문서에 명확히 규칙을 적어야 한다
4. 기존 freq 버킷에서 제거 후 다음 freq 버킷으로 이동
5. 필요 시 `min_freq` 조정

#### (2) 새 key 삽입인 경우
새 key는 아직 사용 이력이 없으므로 일반적으로 `freq = 1`로 시작한다.

1. 메모리 여유 확인
2. 부족하면 eviction 수행
3. `key -> (value, 1, node)` 저장
4. `freq=1` 리스트에 노드 삽입
5. `min_freq = 1`로 설정
   - 새 항목이 들어오면 최소 빈도는 반드시 1이 되기 때문

---

### LFU에서 Eviction 동작 절차

메모리 초과 시 LFU는 다음 순서로 제거 대상을 찾는다.

1. 현재 `min_freq` 값을 확인한다
2. `freq_to_list[min_freq]` 리스트를 찾는다
3. 그 리스트의 **가장 오래된 노드**를 제거한다
   - 같은 빈도 안에서는 LRU tie-break
   - 보통 리스트 뒤쪽을 제거 대상으로 둔다
4. 제거된 노드의 key를 기준으로
   - `key -> entry` 해시맵에서 삭제
   - 해당 빈도 리스트에서도 삭제
   - 메모리 사용량 차감
5. 빈도 리스트가 비면 필요 시 버킷 정리
6. 이후 새 항목 삽입 진행

즉 LFU의 eviction은
- LRU처럼 "전체 리스트의 꼬리 하나 제거"가 아니라
- "`min_freq`가 가리키는 빈도 버킷 안에서 가장 오래된 항목 제거"

라는 차이가 있다.

---

### 왜 이 구조로 O(1) LFU가 가능한가?

핵심은 "탐색"과 "이동"을 분리하는 것이다.

- **탐색**: `key -> entry` 해시맵으로 O(1)
- **빈도 그룹 관리**: `freq -> DoublyLinkedList`로 O(1)
- **최소 빈도 추적**: `min_freq` 변수로 O(1)

따라서
- GET: 해시 조회 + 현재 버킷 제거 + 다음 버킷 삽입
- SET(갱신): 해시 조회 + 버킷 이동
- SET(신규): eviction 후 freq=1 버킷 삽입
- Eviction: `min_freq` 버킷의 tail 제거

가 모두 상수 시간으로 구성된다.

---

### 현재 LRU 구조를 LFU 구조로 바꾼다면 무엇이 달라지는가?

현재는 대략 다음 개념이다.

- `_data`: key -> value
- `_lru_nodes`: key -> LRU 리스트 노드
- `_lru_list`: 최근 사용 순서 전체 관리

LFU로 바꾸면 이런 형태로 재구성된다.

- `_data`: key -> `(value, freq, freq_node)`
- `_freq_lists`: freq -> `DoublyLinkedList`
- `_min_freq`: 현재 최소 빈도
- 필요하면 `_ttl_map`, `_ttl_heap`는 그대로 유지

즉 LRU에서는 "전역 리스트 1개"면 충분했지만,
LFU에서는 "빈도별 리스트 여러 개"가 필요하다.

---

### TTL과 LFU를 함께 쓸 때의 주의점

현재 과제 구조에는 TTL도 있으므로, LFU로 바꾸더라도 다음 규칙은 그대로 중요하다.

1. 먼저 만료 여부를 확인한다
2. 만료되었으면 실제 사용 빈도 증가 없이 삭제 처리한다
3. 살아 있는 경우에만 GET/SET에 따른 freq 갱신을 한다
4. eviction 대상 선정 시에도 이미 만료된 키는 우선 정리되어야 한다

즉 흐름은 보통 다음과 같다.

- 조회 시: TTL 확인 → 만료면 삭제 → 아니면 value 반환 및 freq 증가
- 메모리 초과 시: 먼저 만료 데이터 purge → 그래도 부족하면 LFU eviction

이렇게 해야 "이미 죽은 키가 빈도 구조에 남아 있어 eviction 판단을 왜곡"하는 문제를 막을 수 있다.

---

## Q13. 데이터가 10만 건으로 늘어나면 현재 구조에서 병목이 될 수 있는 부분은 어디이며, 어떻게 개선할 수 있는가? (평가표 항목 4-2)

현재 구현은 과제 범위에서는 충분히 타당하지만, 데이터가 10만 건 수준으로 커지면 몇 가지 지점이 성능 병목으로 드러날 수 있다. 대표적으로 다음 3가지가 중요하다.

### 1) `HashMap._resize`의 일괄 재해싱(Stop-the-world)

현재 `HashMap`은 로드 팩터가 `self._size / self._capacity > 0.75`를 넘으면 `_resize`를 호출해 **버킷을 2배로 늘린 뒤 모든 엔트리를 새 배열로 한 번에 재배치**한다.

이 방식의 문제는 평소에는 빠르지만, 확장 순간에는 다음 작업이 몰아서 발생한다.

- 새 버킷 배열 생성
- 기존 모든 버킷 순회
- 모든 노드 재해싱
- 새 버킷으로 재삽입

데이터가 10만 건이면 이 순간의 비용은 O(N)이며, 명령 처리 한 번이 갑자기 매우 느려질 수 있다.  
즉 시스템 전체가 잠깐 멈춘 것처럼 보이는 **Stop-the-world** 현상이 생긴다.

#### 개선안: Incremental Rehashing
전체 재해싱을 한 번에 하지 말고 **조금씩 나누어 이전**하는 방식이다.

구성 아이디어:
- 기존 버킷 배열 `old_table`
- 새 버킷 배열 `new_table`
- 현재 어디까지 옮겼는지 가리키는 `rehash_idx`

동작 방식:
1. 확장이 필요해지면 새 배열만 먼저 만든다
2. 이후 각 `GET`/`SET`/`DEL` 명령이 들어올 때마다
   - 실제 명령 처리 전 또는 후에
   - 버킷 몇 개씩만 `old_table`에서 `new_table`로 옮긴다
3. 모든 버킷 이전이 끝나면 `new_table`을 정식 테이블로 승격한다

장점:
- 한 번의 긴 멈춤 대신 여러 번의 작은 비용으로 분산
- 지연시간(latency) 급증을 완화

대신 구현은 복잡해진다.
- 조회 시 old/new 두 테이블 모두 확인해야 할 수 있음
- 삽입/삭제가 재해싱 진행 상태와 상호작용함

그래도 대규모 데이터에서는 훨씬 실용적이다.

---

### 2) `KEYS` 명령의 전체 버킷 순회 O(N)

`KEYS`는 저장된 모든 키를 반환해야 하므로 현재 구조상 **모든 버킷과 체인 노드를 전부 순회**해야 한다.  
데이터가 10만 건이면 `KEYS *` 같은 동작은 한 번에 전체 데이터를 훑는 비용이 들어간다.

이 문제는 단순히 "느리다"를 넘어서,
- 다른 명령 처리 지연
- 응답 크기 폭증
- TTL purge나 eviction과 결합 시 추가 부담

으로 이어질 수 있다.

#### 개선안: `SCAN` 커서 기반 순회
Redis가 실제로 `KEYS` 대신 `SCAN` 사용을 권장하는 이유와 같다.

구성 아이디어:
- 한 번에 전체를 반환하지 않고
- "현재 커서 위치부터 일정 개수만" 반환
- 다음 호출 때 이어서 순회

예시 개념:
- `SCAN 0` → 일부 키 + 다음 커서
- `SCAN 128` → 이어서 일부 키 + 다음 커서
- 커서가 다시 0이 되면 순회 종료

장점:
- 한 요청의 비용을 작게 제한 가능
- 대규모 데이터셋에서도 서버 블로킹 감소
- UI/테스트에서도 페이지네이션처럼 다루기 쉬움

현재 과제 요구는 `KEYS` 구현이지만, 10만 건 이상을 고려한다면
실서비스성 관점에서는 `KEYS`는 디버그/소규모용으로 두고,
일반 순회 API는 `SCAN`으로 분리하는 것이 적절하다.

---

### 3) `_ttl_heap`의 Lazy Deletion으로 인한 중복 튜플 누적

현재 TTL 구조는 대략 다음과 같다.

- `_ttl_map`: key -> expire_at
- `_ttl_heap`: `(expire_at, key)` 최소 힙
- `_purge_expired()`: 힙 top을 보며 실제 만료 여부와 `_ttl_map` 최신 값 비교

이 방식은 구현이 단순하고 올바르지만, **같은 key에 EXPIRE가 여러 번 걸리면 힙에 오래된 튜플이 계속 남는다**는 문제가 있다.

예를 들어:
- `EXPIRE a 10`
- `EXPIRE a 20`
- `EXPIRE a 30`

이면 힙에는 `(t1, a)`, `(t2, a)`, `(t3, a)`가 모두 남을 수 있다.  
실제 유효한 것은 마지막 하나뿐이지만, 나머지는 나중에 top으로 올라왔을 때 버려지는 **stale entry**다.

데이터가 많고 TTL 갱신이 잦으면:
- 힙 크기가 실제 live key 수보다 훨씬 커질 수 있고
- `_purge_expired()`가 stale tuple을 여러 번 pop하며 낭비
- 메모리도 불필요하게 사용

#### 개선안 1: Indexed Min-Heap
힙 내부에서 `key -> heap_index`를 함께 관리하는 방식이다.

그러면 특정 key의 TTL 갱신 시:
1. 기존 힙 위치를 찾고
2. 그 원소를 직접 수정하거나 제거한 뒤
3. 새 expire_at으로 재배치

할 수 있다.

장점:
- key당 힙 엔트리를 1개로 유지 가능
- stale tuple 누적 방지
- purge 시 불필요한 pop 감소

단점:
- 일반 최소 힙보다 구현 복잡도가 높음
- swap 시 index map도 함께 갱신해야 함

#### 개선안 2: Active Expire + 주기적 샘플링
또 다른 방법은 힙 의존도를 낮추고, 주기적으로 TTL 키 일부를 샘플링하여 정리하는 것이다.

방식 예:
- 매 명령마다 조금씩 또는 주기적으로
- TTL이 있는 key 몇 개를 무작위/순차 샘플링
- 만료된 것만 삭제
- 짧은 시간 예산 안에서 반복

장점:
- 힙 stale entry 관리 부담 감소
- purge 비용을 분산 가능

단점:
- 엄밀한 "가장 빠른 만료 우선 정리"는 약해질 수 있음
- 만료 직후 샘플링 전까지는 lazy deletion(조회 시 `_is_expired` 검사)과 병행하여 정확성을 보장한다.

---

### Q14. used_memory에 자료구조 오버헤드까지 포함하는 모델로 바꾸면 무엇이 달라지고, 공정한 비교/채점을 위해 어떤 보정이 필요할지 설명할 수 있는가? (평가표 항목 4-3)

`used_memory`를 단순히 **사용자 데이터(키 문자열 길이 + 값 문자열 길이)**만이 아니라, 내부 자료구조의 오버헤드까지 포함하는 방식으로 바꾸면 시스템 동작이 더 현실적이 되지만, 구현체마다 측정 결과가 크게 달라질 수 있다. 특히 이 과제처럼 `HashMap + LRU 이중 연결 리스트 + TTL용 MinHeap`을 함께 쓰는 구조에서는 다음 변화가 생긴다.

#### 1) 오버헤드 포함 시 달라지는 현상

1. **소형 키-값을 많이 넣을 때 조기 축출(eviction)과 OOM이 더 빨리 발생한다.**  
   작은 문자열을 저장하는 경우 실제 payload보다 `Node`의 `prev/next` 포인터, 해시 버킷 참조, TTL 보조 정보, 힙 원소 등이 더 큰 비중을 차지할 수 있다.  
   따라서 겉보기에는 데이터 자체가 작아 보여도 `maxmemory`를 빨리 초과하여 LRU 제거가 더 일찍 발생하고, 심한 경우 삽입 직후 OOM이 날 수도 있다.

2. **모든 키를 삭제해도 `used_memory`가 0에 가깝게 떨어지지 않을 수 있다.**  
   이유는 두 가지다.
   - **확장된 버킷 배열이 유지**될 수 있다. 해시맵은 한 번 커진 뒤 즉시 축소하지 않으면 빈 상태에서도 배열 메모리를 계속 점유한다.
   - **TTL MinHeap의 stale 튜플**이 남을 수 있다. 예를 들어 어떤 키의 만료 시간을 여러 번 갱신하면 이전 힙 원소는 무효가 되었더라도 힙 내부에는 남아 있다가 나중에 정리된다.  
   이 때문에 논리적으로는 빈 저장소라도 내부 구조의 잔여 용량 때문에 `used_memory`가 0으로 수렴하지 않는 현상이 생긴다.

3. **리사이즈 순간 메모리 사용량이 급증한다.**  
   로드 팩터 0.75 초과 시 버킷을 2배로 늘리는 과정에서는, 구현 방식에 따라 **이전 배열과 새 배열이 잠시 동시에 존재**할 수 있다.  
   즉 평상시보다 훨씬 큰 메모리 피크가 순간적으로 발생하며, 이 시점에 `maxmemory` 판정이 매우 민감해진다.  
   데이터 수는 거의 변하지 않았는데도 재해시 순간에만 eviction 또는 OOM이 발생할 수 있다는 점이 기존 모델과 가장 크게 다르다.

#### 2) 공정한 비교/채점을 위한 보정 방안

1. **런타임 의존 `sys.getsizeof` 대신, 명세서에 엔트리당 고정 가상 오버헤드 상수를 공식화해야 한다.**  
   Python의 실제 객체 크기는 버전, 인터프리터, 플랫폼에 따라 달라진다. 따라서 `sys.getsizeof`를 그대로 쓰면 같은 코드라도 환경에 따라 `used_memory` 값이 달라져 채점이 불공정해질 수 있다.  
   더 공정한 방법은 예를 들어 다음처럼 **명세 기반 가상 모델**을 쓰는 것이다.

   - 엔트리 1개당 기본 오버헤드: `ENTRY_OVERHEAD`
   - LRU 노드 오버헤드: `LRU_NODE_OVERHEAD`
   - TTL 설정된 키 1개당 추가 오버헤드: `TTL_ENTRY_OVERHEAD`
   - 힙 원소 1개당 오버헤드: `HEAP_TUPLE_OVERHEAD`

   이렇게 상수 기반 공식으로 계산하면 모든 제출물이 같은 기준으로 비교된다.

2. **버킷 배열과 힙 stale 엔트리의 정산 규칙을 통일해야 한다.**  
   구현마다 “빈 버킷도 메모리로 볼지”, “stale 힙 튜플을 즉시 차감할지, pop될 때 차감할지”가 다르면 결과가 크게 흔들린다.  
   따라서 채점 기준에서 다음을 고정하는 것이 좋다.

   - 버킷 배열은 **현재 capacity 전체를 기준으로 계산**
   - stale 힙 튜플은 **힙 내부에 남아 있는 동안 메모리에 포함**
   - 또는 반대로 **논리적으로 유효한 TTL만 계산**하도록 명시

   핵심은 어떤 방식을 쓰든 모두가 동일 규칙을 따라야 한다는 점이다.

3. **허용 오차 범위(Tolerance)를 둬야 한다.**  
   리사이즈 타이밍, stale 정리 시점, 삭제 직후 즉시 축소 여부 등에 따라 `used_memory`는 구현 세부 차이로 조금씩 달라질 수 있다.  
   그래서 채점에서는 절대값 완전 일치보다 다음과 같은 완충 규칙이 필요하다.

   - `used_memory`는 기준값 대비 ±허용 범위 인정
   - eviction 발생 시점도 1~2개 엔트리 정도 차이를 허용
   - `INFO memory` 검증은 “증가/감소 방향과 대체로 일관된 값” 중심으로 확인

즉, 오버헤드 포함 모델은 더 현실적이지만, 그대로 채점에 쓰면 언어/런타임/구현 선택의 영향이 너무 커진다. 따라서 **고정 상수 기반 가상 메모리 모델 + stale/배열 정산 규칙 통일 + 허용 오차 부여**가 공정한 비교를 위해 필요하다.

## 평가표(b5-1_eval.md) 체크리스트 전체 점검표

| 구분 | 체크리스트 항목 | 상태 | 구현 코드 및 문서 근거 |
|---|---|---|---|
| 항목 1 | String 타입 기본 동작: SET, GET, DEL, EXISTS, DBSIZE, KEYS 명령어가 모두 정상 동작하는가? | 충족 | `mini_redis/commands.py`, `mini_redis/store.py`, `tests/test_mini_redis.py` (`StringCommandsTest`) |
| 항목 1 | LRU 자동 제거: maxmemory 설정 후 제한 초과 시 가장 오래된 키가 자동 제거되는가? | 충족 | `mini_redis/store.py` (`_evict_if_needed`), `tests/test_mini_redis.py` (`MemoryAndLRUTest`) |
| 항목 1 | 메모리 정보 확인: INFO memory에서 used_memory/maxmemory/evicted_keys가 규칙에 맞게 출력되는가? | 충족 | `mini_redis/store.py` (`info_memory`, `_entry_size`), `tests/test_mini_redis.py` (`MemoryAndLRUTest`) |
| 항목 1 | TTL 관리: EXPIRE/TTL 규칙이 동작하며 만료된 키가 적절히 제거되는가? | 충족 | `mini_redis/store.py` (`expire`, `ttl`, `_purge_expired`), `tests/test_mini_redis.py` (`TTLTest`) |
| 항목 1 | 에러 처리: 잘못된 명령/인자/정수 오류/OOM이 표준 형식으로 출력되는가? | 충족 | `mini_redis/errors.py`, `mini_redis/commands.py`, `tests/test_mini_redis.py` (`ErrorHandlingTest`) |
| 항목 2 | 이중 연결 리스트의 노드 구조(prev, next, data)와 핵심 메서드들이 O(1)로 동작하도록 어떻게 구성했는지 설명할 수 있는가? | 충족 | `mini_redis/linked_list.py` (`Node`, `DoublyLinkedList`), `note.md` Q4/Q5 |
| 항목 2 | 해시맵에서 직접 설계한 해시 함수가 어떤 입력을 받아 어떤 과정을 거쳐 인덱스를 만드는지 설명할 수 있는가? | 충족 | `mini_redis/hashmap.py` (`_hash` DJB2 5381), `note.md` Q1 |
| 항목 2 | 충돌 해결을 체이닝 방식으로 어떻게 구현했는지(버킷 내부 구조 선택 포함) 설명할 수 있는가? | 충족 | `mini_redis/hashmap.py` (`_buckets: list[DoublyLinkedList]`), `note.md` Q2 |
| 항목 2 | 로드 팩터 0.75 초과 시 "버킷 2배 확장"을 어떤 절차로 수행하는지 설명할 수 있는가? | 충족 | `mini_redis/hashmap.py` (`_resize`), `note.md` Q3 |
| 항목 3 | LRU 구현에서 "해시맵 + 이중 연결 리스트"가 각각 어떤 역할을 하고, 왜 둘 다 필요한지 설명할 수 있는가? | 충족 | `mini_redis/store.py` (`_lru_nodes` + `_lru_list`), `note.md` Q4 |
| 항목 3 | O(1) LRU 달성 원리를 "조회(해시) + 갱신(리스트 이동)" 관점에서 설명할 수 있는가? | 충족 | `mini_redis/store.py` (`set`, `get`의 `move_to_front`), `note.md` Q4/Q5 |
| 항목 3 | TTL 관리에 힙을 사용한 이유(가장 빠른 만료를 빠르게 찾는 성질)를 설명할 수 있는가? | 충족 | `mini_redis/heap.py` (`MinHeap`), `mini_redis/store.py` (`_purge_expired`), `note.md` Q6/Q7 |
| 항목 3 | 메모리 초과 시 eviction 흐름을 단계별로 설명할 수 있는가? (used_memory 산정/갱신, LRU 제거, evicted_keys 증가 포함) | 충족 | `mini_redis/store.py` (`_evict_if_needed`, `_entry_size`), `note.md` Q10/Q11 |
| 항목 3 | GET 명령어 전체 흐름을 순서대로 설명할 수 있는가? (TTL 확인 → 삭제 여부 → 값 반환 → LRU 갱신 조건) | 충족 | `mini_redis/store.py` (`get`, `_is_expired`), `note.md` Q9 |
| 항목 4 | "만약 LRU 대신 LFU 정책을 구현한다면 자료구조를 어떻게 변경해야 하는가?"에 합리적으로 답변할 수 있는가? | 충족 | `note.md` Q12 (`key->(val,freq,node)` + `freq->DoublyLinkedList` + `min_freq`) |
| 항목 4 | "데이터가 10만 건으로 늘어나면 현재 구조에서 병목이 될 수 있는 부분은 어디이며, 어떻게 개선할 수 있는가?"에 답변할 수 있는가? | 충족 | `note.md` Q13 (점진적 리해싱, `SCAN` 커서, Indexed Min-Heap/Active Expire) |
| 항목 4 | "used_memory에 자료구조 오버헤드까지 포함하는 모델로 바꾸면 무엇이 달라지고, 공정한 비교/채점을 위해 어떤 보정이 필요할지" 설명할 수 있는가? | 충족 | `note.md` Q14 (가상 오버헤드 상수 공식화, 정산 규칙 통일, 허용 오차 범위) |
