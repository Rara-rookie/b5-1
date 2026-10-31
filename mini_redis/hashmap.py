from .linked_list import DoublyLinkedList, Node


class HashMap:
    """이중 연결 리스트 체이닝으로 충돌을 해결하는 문자열 키 기반 해시맵이다."""

    def __init__(self, initial_capacity: int = 8) -> None:
        """초기 버킷 배열을 준비한다.

        용량이 1 미만이면 너무 작은 테이블로 인한 즉시 리사이즈를 피하기 위해 기본값 8을 사용한다.
        각 버킷을 독립적인 연결 리스트로 만들어 충돌 시에도 삽입과 삭제 규칙을 단순하게 유지한다.
        """
        capacity = initial_capacity
        if capacity < 1:
            capacity = 8
        self._capacity: int = capacity
        self._size: int = 0
        self._buckets: list[DoublyLinkedList] = [DoublyLinkedList() for _ in range(self._capacity)]

    def _hash(self, key: str) -> int:
        """문자열 키를 현재 버킷 범위 안의 인덱스로 변환한다.

        djb2는 구현이 단순하면서 문자열에 대해 비교적 고른 분산을 제공하므로
        교육용 해시맵에서 해시 원리를 드러내기에 적합하다.
        """
        hash_value = 5381
        for char in key:
            hash_value = ((hash_value << 5) + hash_value) + ord(char)
        return hash_value % self._capacity

    def put(self, key: str, value: object) -> None:
        """키에 값을 저장하거나 기존 키의 값을 갱신한다.

        같은 키가 이미 있으면 항목 수를 늘리지 않고 값만 바꿔야
        size와 로드 팩터가 실제 엔트리 개수를 정확히 반영한다.
        새 키를 추가한 뒤 로드 팩터가 임계값을 넘으면 조회 성능 악화를 늦추기 위해 리사이즈한다.
        """
        index = self._hash(key)
        bucket = self._buckets[index]

        current = bucket.head
        while current is not None:
            entry = current.data
            if entry[0] == key:
                current.data = (key, value)
                return
            current = current.next

        bucket.insert_back((key, value))
        self._size += 1

        if self._size / self._capacity > 0.75:
            self._resize()

    def get(self, key: str) -> object | None:
        """키에 대응하는 값을 반환하고, 없으면 None을 반환한다.

        해시가 가리키는 버킷만 순회하도록 제한하는 이유는
        전체 데이터를 매번 탐색하는 선형 비용을 피하기 위해서이다.
        """
        index = self._hash(key)
        bucket = self._buckets[index]

        current = bucket.head
        while current is not None:
            entry = current.data
            if entry[0] == key:
                return entry[1]
            current = current.next

        return None

    def remove(self, key: str) -> bool:
        """키에 해당하는 항목을 제거하고 성공 여부를 반환한다.

        체이닝 구조에서는 같은 버킷 안에서만 키를 찾으면 되며,
        노드를 직접 제거할 수 있어 찾은 뒤의 삭제 비용을 O(1)로 유지할 수 있다.
        """
        index = self._hash(key)
        bucket = self._buckets[index]

        current: Node | None = bucket.head
        while current is not None:
            entry = current.data
            if entry[0] == key:
                bucket.remove_node(current)
                self._size -= 1
                return True
            current = current.next

        return False

    def contains(self, key: str) -> bool:
        """주어진 키의 존재 여부만 확인한다.

        값을 꺼낼 필요가 없는 호출에서 get과 의도를 분리해 두면
        None이 실제 저장값일 가능성과 미존재를 혼동하지 않게 된다.
        """
        index = self._hash(key)
        bucket = self._buckets[index]

        current = bucket.head
        while current is not None:
            entry = current.data
            if entry[0] == key:
                return True
            current = current.next

        return False

    def keys(self) -> list[str]:
        """현재 저장된 모든 키를 리스트로 반환한다.

        버킷 순서와 체이닝 순서를 그대로 따르는 이유는
        추가 메모리나 정렬 비용 없이 테이블의 실제 저장 상태를 그대로 노출하기 위해서이다.
        """
        result: list[str] = []
        bucket_index = 0
        while bucket_index < self._capacity:
            current = self._buckets[bucket_index].head
            while current is not None:
                entry = current.data
                result.append(entry[0])
                current = current.next
            bucket_index += 1
        return result

    def size(self) -> int:
        """현재 해시맵에 저장된 고유 키의 개수를 반환한다.

        호출마다 다시 세지 않고 누적 값을 유지하는 이유는
        크기 조회가 자주 일어나도 항상 O(1)로 응답하기 위해서이다.
        """
        return self._size

    def _resize(self) -> None:
        """버킷 배열을 두 배로 확장하고 기존 엔트리를 새 버킷에 재배치한다.

        리사이즈 중에는 모든 엔트리가 이미 고유 키라는 사실이 보장되므로
        put을 다시 호출해 중복 키 탐색을 반복할 이유가 없다.
        새 해시값에 맞는 버킷 뒤에 바로 삽입하면 전체 리해싱을 O(N)으로 유지할 수 있다.
        """
        old_buckets = self._buckets
        old_capacity = self._capacity

        self._capacity *= 2
        self._buckets = [DoublyLinkedList() for _ in range(self._capacity)]

        bucket_index = 0
        while bucket_index < old_capacity:
            current = old_buckets[bucket_index].head
            while current is not None:
                entry = current.data
                self._buckets[self._hash(entry[0])].insert_back(entry)
                current = current.next
            bucket_index += 1
