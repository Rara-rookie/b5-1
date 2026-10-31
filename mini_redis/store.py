import math
import time

from .errors import OOMError
from .hashmap import HashMap
from .heap import MinHeap
from .linked_list import DoublyLinkedList, Node


class MiniRedisStore:
    """해시맵, LRU 리스트, TTL 최소 힙을 결합한 핵심 저장소 엔진이다."""

    def __init__(self, now_fn: 'object' = None) -> None:
        """저장소의 모든 인덱스와 통계를 초기화한다.

        테스트에서는 시간을 고정해야 TTL 동작을 안정적으로 검증할 수 있으므로
        외부에서 현재 시각 함수를 주입할 수 있게 둔다.
        데이터 본문, TTL 정보, LRU 노드 참조를 분리해 저장하는 이유는
        조회/만료/축출을 각각 필요한 구조에서 O(1) 또는 로그 시간으로 처리하기 위해서이다.
        """
        self._now_fn = now_fn if now_fn is not None else time.time

        self._data: HashMap = HashMap()
        self._ttl_map: HashMap = HashMap()
        self._lru_nodes: HashMap = HashMap()
        self._lru_list: DoublyLinkedList = DoublyLinkedList()
        self._ttl_heap: MinHeap = MinHeap()

        self._used_memory: int = 0
        self._maxmemory: int = 0
        self._evicted_keys: int = 0

    def set(self, key: str, value: str) -> None:
        """키에 값을 저장하고 필요하면 LRU와 메모리 상태를 갱신한다.

        쓰기 전에 먼저 만료된 키를 정리해야 이미 사용 불가능한 데이터가
        메모리를 계속 점유하며 잘못된 OOM 판단을 만드는 일을 막을 수 있다.
        기존 키를 덮어쓸 때는 이전 값의 크기를 먼저 차감해 실제 사용량을 정확히 유지한다.
        SET은 기존 TTL을 제거하는 Redis 계열 규칙을 따르므로 저장 성공 후 TTL 맵에서 지운다.
        마지막으로 키를 LRU 최전방으로 이동시키고, 메모리 제한을 넘으면 후순위 키를 축출한다.
        새 항목 하나만으로도 제한을 절대 만족시킬 수 없는 경우는 축출로 해결할 수 없으므로 OOMError를 발생시킨다.
        축출 도중 실패하면 방금 넣은 키를 롤백해 부분 반영 상태를 남기지 않는다.
        """
        self._purge_expired()

        new_entry_size = self._entry_size(key, value)
        if self._maxmemory > 0 and new_entry_size > self._maxmemory:
            raise OOMError()

        old_value = self._data.get(key)
        old_exists = old_value is not None

        if old_exists:
            self._used_memory -= self._entry_size(key, old_value)

        self._data.put(key, value)
        self._used_memory += new_entry_size

        if self._ttl_map.contains(key):
            self._ttl_map.remove(key)

        lru_node = self._lru_nodes.get(key)
        if lru_node is None:
            new_node = self._lru_list.insert_front(key)
            self._lru_nodes.put(key, new_node)
        else:
            self._lru_list.move_to_front(lru_node)

        try:
            self._evict_if_needed()
        except OOMError:
            if self._data.contains(key):
                self._delete_key_internal(key)
            raise

    def get(self, key: str) -> str | None:
        """키의 값을 조회하고, 존재하면 해당 키를 최근 사용 상태로 만든다.

        조회 전에 만료 여부를 검사하는 이유는
        이미 TTL이 지난 키를 살아 있는 데이터처럼 반환하지 않기 위해서이다.
        값이 존재하면 LRU 노드를 리스트 앞쪽으로 이동시켜
        메모리 압박 시 최근 접근한 키가 덜 축출되도록 한다.
        """
        if self._is_expired(key):
            return None

        value = self._data.get(key)
        if value is None:
            return None

        lru_node = self._lru_nodes.get(key)
        if lru_node is not None:
            self._lru_list.move_to_front(lru_node)

        return value

    def delete(self, key: str) -> int:
        """키를 삭제하고 실제로 제거되었는지 1 또는 0으로 반환한다.

        이미 만료된 키는 조회 가능한 데이터가 아니므로
        명시 삭제 대상이 아니라 없는 키와 같은 결과를 돌려준다.
        내부 삭제 루틴 하나로 메모리, TTL, LRU를 함께 정리해야
        구조 간 불일치가 누적되지 않는다.
        """
        if self._is_expired(key):
            return 0

        if not self._data.contains(key):
            return 0

        self._delete_key_internal(key)
        return 1

    def exists(self, key: str) -> int:
        """키가 현재 유효하게 존재하면 1, 아니면 0을 반환한다.

        TTL이 지난 키를 선제적으로 제거해야
        존재 확인이 오래된 힙 정리 여부에 따라 달라지는 문제를 피할 수 있다.
        반환형을 정수로 고정하는 이유는 Redis 스타일 명령 결과와 맞추기 위해서이다.
        """
        if self._is_expired(key):
            return 0
        if self._data.contains(key):
            return 1
        return 0

    def dbsize(self) -> int:
        """만료 정리 후 현재 저장된 유효 키 개수를 반환한다.

        정리 없이 크기만 읽으면 힙에는 만료 정보가 있으나 데이터에도 아직 남아 있는
        지연 삭제 항목이 카운트될 수 있으므로 먼저 purge를 수행한다.
        """
        self._purge_expired()
        return self._data.size()

    def keys(self) -> list[str]:
        """만료 정리 후 현재 유효한 모든 키 목록을 반환한다.

        지연 삭제 구조에서는 만료된 키가 내부 해시맵에 잠시 남아 있을 수 있으므로
        외부에 키 목록을 노출하기 전에 purge를 실행해 관찰 가능한 상태를 맞춘다.
        """
        self._purge_expired()
        return self._data.keys()

    def set_maxmemory(self, bytes_limit: int) -> None:
        """최대 메모리 한도를 설정하고 즉시 초과분을 해소한다.

        제한을 낮춘 직후에도 초과 상태를 그대로 두면
        이후 명령에서야 뒤늦게 실패하거나 축출되어 일관성이 떨어지므로 즉시 정리한다.
        먼저 만료 키를 제거하는 이유는
        실제로는 버려도 될 데이터를 축출 카운트에 포함하지 않기 위해서이다.
        """
        self._maxmemory = bytes_limit
        self._purge_expired()
        self._evict_if_needed()

    def info_memory(self) -> tuple[int, int, int]:
        """현재 사용 메모리, 최대 메모리, 누적 축출 키 수를 반환한다.

        정보 조회도 외부에 보이는 관리 지표이므로
        만료 데이터를 포함한 낡은 수치를 보여주지 않기 위해 먼저 purge를 수행한다.
        """
        self._purge_expired()
        return (self._used_memory, self._maxmemory, self._evicted_keys)

    def expire(self, key: str, seconds: int) -> int:
        """키에 TTL을 설정하고 성공 여부를 1 또는 0으로 반환한다.

        존재하지 않거나 이미 만료된 키에는 TTL을 붙일 수 없으므로 0을 반환한다.
        TTL이 0 이하이면 미래 시각을 기록할 이유가 없으므로 즉시 삭제해
        호출 시점 이후에 키가 남지 않도록 보장한다.
        양수 TTL은 만료 시각을 TTL 맵과 최소 힙에 함께 기록한다.
        힙에는 같은 키의 오래된 만료 항목이 남을 수 있지만,
        purge 시 현재 TTL 맵 값과 비교해 최신 항목만 실제 삭제에 사용한다.
        """
        if self._is_expired(key):
            return 0

        if not self._data.contains(key):
            return 0

        if seconds <= 0:
            self._delete_key_internal(key)
            return 1

        expire_at = float(self._now_fn()) + float(seconds)
        self._ttl_map.put(key, expire_at)
        self._ttl_heap.push((expire_at, key))
        return 1

    def ttl(self, key: str) -> int:
        """키의 남은 TTL을 Redis 호환 규칙에 맞춰 반환한다.

        키가 없거나 조회 시점에 이미 만료되었으면 -2를 반환한다.
        키는 있지만 만료 설정이 없으면 -1을 반환한다.
        양수 TTL이 있으면 초 단위 올림을 사용해 계산하는데,
        이는 아직 남아 있는 부분 초를 0으로 잘라 조기 만료처럼 보이지 않게 하기 위해서이다.
        """
        if self._is_expired(key):
            return -2

        if not self._data.contains(key):
            return -2

        expire_at = self._ttl_map.get(key)
        if expire_at is None:
            return -1

        remaining = max(0, int(math.ceil(expire_at - float(self._now_fn()))))
        return remaining

    def _is_expired(self, key: str) -> bool:
        """주어진 키가 현재 시각 기준으로 만료되었는지 판정한다.

        먼저 전체 purge를 실행하는 이유는
        힙 루트에 도달한 다른 만료 키들을 함께 정리해 전역 상태를 최신으로 맞추기 위해서이다.
        그 뒤 특정 키의 TTL을 직접 다시 확인하는 이유는
        힙에는 최신화 과정에서 생긴 오래된 항목이 남아 있을 수 있기 때문이다.
        만료가 확인되면 즉시 내부 삭제를 수행해 같은 키가 이후 연산마다 반복 검사되지 않게 한다.
        """
        self._purge_expired()

        expire_at = self._ttl_map.get(key)
        if expire_at is None:
            return False

        now = float(self._now_fn())
        if expire_at <= now:
            self._delete_key_internal(key)
            return True

        return False

    def _evict_if_needed(self) -> None:
        """사용 메모리가 한도를 넘는 동안 LRU 기준으로 키를 축출한다.

        축출 전에 만료 키를 먼저 제거해야
        실제로는 이미 무효한 데이터를 최근 사용 여부와 무관하게 공짜로 정리할 수 있다.
        maxmemory가 0 이하이면 제한이 없다는 뜻으로 보고 아무 작업도 하지 않는다.
        초과 상태에서는 LRU 리스트의 뒤쪽, 즉 가장 오래 사용되지 않은 키부터 제거한다.
        리스트에는 있으나 데이터 맵에는 없는 비정상 상태를 남기지 않도록
        LRU 노드 참조와 본문 데이터를 함께 정리한다.
        리스트가 비어 더 이상 지울 항목이 없는데도 초과가 해소되지 않으면
        호출자가 실패를 감지할 수 있도록 OOMError를 발생시킨다.
        """
        self._purge_expired()

        if self._maxmemory <= 0:
            return

        while self._used_memory > self._maxmemory:
            lru_key = self._lru_list.remove_back()
            if lru_key is None:
                raise OOMError()

            self._lru_nodes.remove(lru_key)
            if self._data.contains(lru_key):
                value = self._data.get(lru_key)
                if value is not None:
                    self._used_memory -= self._entry_size(lru_key, value)
                self._data.remove(lru_key)
                if self._ttl_map.contains(lru_key):
                    self._ttl_map.remove(lru_key)
                self._evicted_keys += 1

    def _entry_size(self, key: str, value: str) -> int:
        """키와 값을 UTF-8 바이트 길이 합으로 환산해 엔트리 크기를 계산한다.

        문자열 길이가 아니라 인코딩된 바이트 수를 써야
        한글 같은 멀티바이트 문자가 실제 메모리 제한 판단에서 과소 계산되지 않는다.
        """
        return len(key.encode("utf-8")) + len(value.encode("utf-8"))

    def _delete_key_internal(self, key: str) -> None:
        """키와 관련된 본문, TTL, LRU 정보를 한 번에 제거한다.

        삭제 경로가 여러 곳에 흩어지면 메모리 차감, TTL 제거, 리스트 정리가 서로 어긋나기 쉬우므로
        공통 루틴으로 묶어 모든 제거 연산이 같은 후처리를 거치게 한다.
        값이 실제로 존재할 때만 메모리 사용량을 차감하는 이유는
        중복 삭제 호출에서도 통계가 음수로 흐트러지지 않게 하기 위해서이다.
        """
        value = self._data.get(key)
        if value is not None:
            self._used_memory -= self._entry_size(key, value)
            self._data.remove(key)

        if self._ttl_map.contains(key):
            self._ttl_map.remove(key)

        lru_node = self._lru_nodes.get(key)
        if lru_node is not None:
            self._lru_list.remove_node(lru_node)
            self._lru_nodes.remove(key)

    def _purge_expired(self) -> None:
        """최소 힙을 이용해 현재 시각까지 만료된 키를 모두 정리한다.

        힙의 루트만 확인하면 가장 이른 만료 시각을 알 수 있으므로
        아직 루트가 미래라면 그 뒤 항목도 전부 미래라는 성질을 이용해 즉시 종료할 수 있다.
        같은 키에 대해 EXPIRE가 여러 번 호출되면 힙에는 예전 만료 항목이 남을 수 있으므로
        팝한 값이 TTL 맵의 현재 만료 시각과 다르면 오래된 기록으로 보고 건너뛴다.
        최신 항목과 일치할 때만 실제 삭제를 수행해야
        TTL 연장이 과거 힙 항목 때문에 무효화되지 않는다.
        """
        now = float(self._now_fn())

        while self._ttl_heap.size() > 0:
            item = self._ttl_heap.peek()
            if item is None:
                return

            expire_at, key = item
            if expire_at > now:
                return

            self._ttl_heap.pop()
            current_expire_at = self._ttl_map.get(key)
            if current_expire_at is None:
                continue
            if current_expire_at != expire_at:
                continue
            self._delete_key_internal(key)
