class Node:
    """이중 연결 리스트의 노드이다."""

    def __init__(self, data: object) -> None:
        """데이터를 담는 노드를 초기화한다. 노드 생성은 포인터 대입만 수행하므로 O(1)이다."""
        self.data: object = data
        self.prev: 'Node | None' = None
        self.next: 'Node | None' = None


class DoublyLinkedList:
    """O(1) 포인터 재연결로 앞뒤 삽입, 삭제, 이동을 지원하는 이중 연결 리스트이다."""

    def __init__(self) -> None:
        """빈 리스트를 초기화한다. head와 tail 설정만 수행하므로 O(1)이다."""
        self.head: Node | None = None
        self.tail: Node | None = None

    def insert_front(self, data: object) -> Node:
        """리스트 맨 앞에 새 노드를 삽입한다. 포인터 몇 개만 갱신하므로 O(1)이다."""
        node = Node(data)
        node.next = self.head
        if self.head is not None:
            self.head.prev = node
        else:
            self.tail = node
        self.head = node
        return node

    def insert_back(self, data: object) -> Node:
        """리스트 맨 뒤에 새 노드를 삽입한다. 포인터 몇 개만 갱신하므로 O(1)이다."""
        node = Node(data)
        node.prev = self.tail
        if self.tail is not None:
            self.tail.next = node
        else:
            self.head = node
        self.tail = node
        return node

    def remove_front(self) -> object | None:
        """리스트 맨 앞 노드를 제거하고 그 데이터를 반환한다. 포인터 몇 개만 갱신하므로 O(1)이다."""
        if self.head is None:
            return None

        node = self.head
        self.head = node.next

        if self.head is not None:
            self.head.prev = None
        else:
            self.tail = None

        node.prev = None
        node.next = None
        return node.data

    def remove_back(self) -> object | None:
        """리스트 맨 뒤 노드를 제거하고 그 데이터를 반환한다. 포인터 몇 개만 갱신하므로 O(1)이다."""
        if self.tail is None:
            return None

        node = self.tail
        self.tail = node.prev

        if self.tail is not None:
            self.tail.next = None
        else:
            self.head = None

        node.prev = None
        node.next = None
        return node.data

    def remove_node(self, node: Node) -> None:
        """주어진 노드를 리스트에서 제거한다. 탐색 없이 이웃 포인터만 재연결하므로 O(1)이다."""
        if node.prev is not None:
            node.prev.next = node.next
        else:
            self.head = node.next

        if node.next is not None:
            node.next.prev = node.prev
        else:
            self.tail = node.prev

        node.prev = None
        node.next = None

    def move_to_front(self, node: Node) -> None:
        """주어진 노드를 리스트 맨 앞으로 이동한다. 탐색 없이 포인터만 재배치하므로 O(1)이다."""
        if node is self.head:
            return

        if node.prev is not None:
            node.prev.next = node.next
        if node.next is not None:
            node.next.prev = node.prev
        else:
            self.tail = node.prev

        node.prev = None
        node.next = self.head

        if self.head is not None:
            self.head.prev = node
        else:
            self.tail = node

        self.head = node

    def is_empty(self) -> bool:
        """리스트가 비어 있는지 확인한다. head 존재 여부만 검사하므로 O(1)이다."""
        return self.head is None

    def __iter__(self) -> object:
        """앞에서 뒤 순서로 데이터를 순회한다. 각 단계 이동은 O(1)이며 전체는 원소 수에 비례한다."""
        current = self.head
        while current is not None:
            yield current.data
            current = current.next
