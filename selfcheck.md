| 요구사항 | 상태 | 근거 |
|---|---|---|
| 이중 연결 리스트 노드 prev/next/data 필드 | 충족 | linked_list.py `Node.__init__`에 data, prev, next 정의 |
| 이중 연결 리스트 메서드 6종(insert_front/back, remove_front/back, remove_node, move_to_front) | 충족 | linked_list.py에 6개 메서드 모두 구현, 포인터 재연결로 O(1) |
| 해시맵 메서드 6종(put/get/remove/contains/keys/size) | 충족 | hashmap.py에 6개 메서드 모두 구현 |
| 해시 함수 직접 설계 | 충족 | hashmap.py `_hash`에 djb2 방식(5381, <<5) 직접 구현 |
| 충돌 해결 체이닝(이중 연결 리스트 재사용) | 충족 | hashmap.py `_buckets`가 DoublyLinkedList 리스트, 버킷 순회로 처리 |
| 로드 팩터 0.75 초과 시 2배 확장 | 충족 | hashmap.py `put`에서 `size/capacity > 0.75`시 `_resize`로 capacity*2 |
| 힙 메서드 4종(push/pop/peek/size)+heapify_up/down | 충족 | heap.py에 push/pop/peek/size 및 `_heapify_up`/`_heapify_down` 구현 |
| 힙 (expire_at, key) 튜플 처리 | 충족 | heap.py 타입 `tuple[float, str]`, store.py `_ttl_heap.push((expire_at, key))` |
| SET 성공 시 OK, LRU 갱신 | 충족 | 실행 `SET user:1 "Alice"`→`OK`, store.set에서 insert_front/move_to_front |
| SET 덮어쓰기 시 기존 TTL 초기화 | 충족 | store.set에서 `if self._ttl_map.contains(key): self._ttl_map.remove(key)` |
| GET 없음/만료 시 (nil), 존재 시 "value" | 충족 | 실행 `GET user:1`→`"Alice"`, LRU 제거된 키 `GET user:1`→`(nil)` |
| GET 성공 시에만 LRU 갱신 | 충족 | store.get에서 만료/None이면 early return, 성공 시 move_to_front |
| DEL 성공 1, 없으면 0 | 충족 | 실행 `DEL a`→`(integer) 1`, 그 후 `EXISTS a`→`(integer) 0` |
| DEL 시 LRU/TTL 함께 제거 | 충족 | store `_delete_key_internal`에서 data/ttl_map/lru 모두 제거 |
| EXISTS 1/0 | 충족 | 실행 `EXISTS a`→1, 삭제 후 →0 |
| DBSIZE (integer) N | 충족 | 실행 `DBSIZE`→`(integer) 1` |
| KEYS 배열/빈 배열 출력 | 충족 | commands.py에 번호 매김 출력 및 `(empty array)` 처리 |
| CONFIG SET maxmemory (0=무제한, 파싱 실패 에러) | 충족 | commands.py `_parse_int` 및 store `_maxmemory<=0`시 evict skip |
| INFO memory 3항목 출력 | 충족 | 실행 `INFO memory`→`used_memory:22 / maxmemory:30 / evicted_keys:1` |
| used_memory 공식(Σ utf8 len) | 충족 | store `_entry_size`=`len(key.utf8)+len(value.utf8)` |
| LRU 초과 제거 및 evicted_keys 카운트 | 충족 | 실행 결과 user:1 제거, `evicted_keys:1` 출력 |
| 단일 엔트리>maxmemory 시 저장 안 하고 OOM | 충족 | store.set에서 `new_entry_size > maxmemory`시 OOMError raise |
| EXPIRE 없는 키 0, 0이하 즉시만료 1, 정상 1 | 충족 | store.expire에 각 케이스 구현, 실행 `EXPIRE k 100`→`(integer) 1` |
| TTL -2/-1/N | 충족 | 실행 `TTL nope`→-2, `TTL k`(무TTL)→-1, `TTL k`→100 |
| TTL 만료 힙 기반 빠른 조회 | 충족 | store `_purge_expired`가 힙 peek로 최소 만료 확인, lazy deletion |
| CLI 프롬프트/파싱/종료(exit,quit) | 충족 | cli.py `mini-redis> ` 프롬프트, exit/quit 종료, EOF 처리 |
| 에러 표준(unknown/wrong args/not integer/OOM) | 충족 | 실행 `HELLO`→unknown, `GET`→wrong args, `abc`→not integer, errors.py에 OOM |
| 값 파싱(따옴표/공백없음) | 충족 | parser.py `tokenize`에서 큰따옴표 및 공백 구분 처리 |
| dict/set/collections 미사용 | 충족 | 모든 파일에서 해당 import 없음, HashMap 직접 구현 사용 |
| 자료구조 독립 모듈 분리 | 충족 | linked_list.py, hashmap.py, heap.py 각각 분리 |
| 핵심 클래스/함수 docstring | 충족 | 각 클래스에 docstring 존재(HashMap, MinHeap, MiniRedisStore 등) |
