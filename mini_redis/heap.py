class MinHeap:
    """TTL 만료 시각이 가장 이른 항목을 빠르게 찾기 위한 배열 기반 최소 힙이다."""

    def __init__(self) -> None:
        """빈 최소 힙을 초기화한다.

        내부 저장소를 빈 배열로 준비만 하므로 시간 복잡도는 O(1)이다.
        """
        self._data: list[tuple[float, str]] = []

    def push(self, item: tuple[float, str]) -> None:
        """새 (expire_at, key) 항목을 힙에 삽입한다.

        새 항목은 배열 끝에 추가한 뒤 부모와 비교하며 위로 올려
        가장 작은 만료 시각이 루트에 오도록 힙 속성을 복구한다.
        시간 복잡도는 최악의 경우 힙 높이에 비례하는 O(log n)이다.
        """
        self._data.append(item)
        self._heapify_up(len(self._data) - 1)

    def pop(self) -> tuple[float, str] | None:
        """루트에 있는 최소 항목을 제거하고 반환한다.

        힙이 비어 있으면 None을 반환한다.
        루트를 꺼낸 뒤 마지막 항목을 루트로 옮기고 아래로 내려 보내
        최소 힙 조건을 다시 만족시킨다.
        시간 복잡도는 원소가 있을 때 최악의 경우 O(log n)이며,
        빈 힙 검사와 단일 원소 처리만 필요한 경우는 O(1)이다.
        """
        if not self._data:
            return None
        if len(self._data) == 1:
            return self._data.pop()

        root: tuple[float, str] = self._data[0]
        last: tuple[float, str] = self._data.pop()
        self._data[0] = last
        self._heapify_down(0)
        return root

    def peek(self) -> tuple[float, str] | None:
        """루트의 최소 항목을 제거하지 않고 반환한다.

        가장 빠른 만료 대상을 확인만 해야 할 때 재정렬 비용을 피하기 위해
        배열의 첫 원소만 읽는다.
        시간 복잡도는 O(1)이다.
        """
        if not self._data:
            return None
        return self._data[0]

    def size(self) -> int:
        """현재 힙에 저장된 항목 수를 반환한다.

        배열 길이 정보만 읽으면 되므로 시간 복잡도는 O(1)이다.
        """
        return len(self._data)

    def _heapify_up(self, index: int) -> None:
        """주어진 인덱스의 항목을 위로 이동시켜 힙 속성을 복구한다.

        삽입 직후에는 새 항목 하나만 부모보다 작을 수 있으므로
        필요한 동안 부모와 교환하며 위로 올리는 편이 가장 단순하고 효율적이다.
        시간 복잡도는 최악의 경우 힙 높이에 비례하는 O(log n)이다.
        """
        while index > 0:
            parent: int = (index - 1) // 2
            if self._data[index] < self._data[parent]:
                self._data[index], self._data[parent] = self._data[parent], self._data[index]
                index = parent
            else:
                break

    def _heapify_down(self, index: int) -> None:
        """주어진 인덱스의 항목을 아래로 이동시켜 힙 속성을 복구한다.

        루트 교체 뒤에는 현재 항목이 자식보다 클 수 있으므로
        두 자식 중 더 작은 쪽과 교환하며 내려 보내야 전체 최소 힙 조건을 유지할 수 있다.
        시간 복잡도는 최악의 경우 힙 높이에 비례하는 O(log n)이다.
        """
        length: int = len(self._data)

        while True:
            left: int = index * 2 + 1
            right: int = index * 2 + 2
            smallest: int = index

            if left < length and self._data[left] < self._data[smallest]:
                smallest = left
            if right < length and self._data[right] < self._data[smallest]:
                smallest = right

            if smallest == index:
                break

            self._data[index], self._data[smallest] = self._data[smallest], self._data[index]
            index = smallest
