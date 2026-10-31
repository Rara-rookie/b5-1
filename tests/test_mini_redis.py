import subprocess
import sys
import unittest

from mini_redis.commands import execute
from mini_redis.hashmap import HashMap
from mini_redis.heap import MinHeap
from mini_redis.linked_list import DoublyLinkedList, Node
from mini_redis.parser import tokenize
from mini_redis.store import MiniRedisStore


class FakeClock:
    """테스트에서 시간을 결정론적으로 제어하기 위한 가짜 시계."""

    def __init__(self, initial: float = 0.0) -> None:
        """초기 시각을 설정한다."""
        self.current = float(initial)

    def now(self) -> float:
        """현재 시각을 반환한다."""
        return self.current

    def advance(self, seconds: float) -> None:
        """원하는 만큼 시각을 전진시킨다."""
        self.current += float(seconds)


def run(store: MiniRedisStore, line: str) -> str:
    """한 줄 명령을 실제 CLI 계층과 같은 경로로 실행한다."""
    return execute(store, tokenize(line))


class DoublyLinkedListTest(unittest.TestCase):
    """이중 연결 리스트의 핵심 연산과 경계 조건을 검증한다."""

    def _values(self, linked_list: DoublyLinkedList) -> list:
        """리스트를 앞에서 뒤로 순회한 값 목록을 만든다."""
        values = []
        node = linked_list.head
        while node is not None:
            values.append(node.data)
            node = node.next
        return values

    def test_insert_front_and_back(self) -> None:
        """양끝 삽입이 head/tail과 순서를 올바르게 유지하는지 확인한다."""
        linked_list = DoublyLinkedList()

        front_node = linked_list.insert_front("b")
        back_node = linked_list.insert_back("c")
        linked_list.insert_front("a")

        self.assertEqual(["a", "b", "c"], self._values(linked_list))
        self.assertEqual("a", linked_list.head.data)
        self.assertEqual("c", linked_list.tail.data)
        self.assertIs(linked_list.head.next, front_node)
        self.assertIs(linked_list.tail, back_node)

    def test_remove_front_and_back(self) -> None:
        """양끝 삭제가 값을 반환하고 마지막 노드 처리도 안정적인지 확인한다."""
        linked_list = DoublyLinkedList()
        linked_list.insert_back("a")
        linked_list.insert_back("b")
        linked_list.insert_back("c")

        front = linked_list.remove_front()
        back = linked_list.remove_back()
        middle = linked_list.remove_front()
        empty_front = linked_list.remove_front()
        empty_back = linked_list.remove_back()

        self.assertEqual("a", front)
        self.assertEqual("c", back)
        self.assertEqual("b", middle)
        self.assertIsNone(empty_front)
        self.assertIsNone(empty_back)
        self.assertIsNone(linked_list.head)
        self.assertIsNone(linked_list.tail)

    def test_remove_node_updates_neighbors_and_boundaries(self) -> None:
        """임의 노드 삭제가 이웃 연결과 끝 포인터를 함께 정리하는지 확인한다."""
        linked_list = DoublyLinkedList()
        first = linked_list.insert_back("a")
        middle = linked_list.insert_back("b")
        last = linked_list.insert_back("c")

        linked_list.remove_node(middle)
        self.assertEqual(["a", "c"], self._values(linked_list))
        self.assertIs(first.next, last)
        self.assertIs(last.prev, first)

        linked_list.remove_node(first)
        self.assertEqual(["c"], self._values(linked_list))
        self.assertEqual("c", linked_list.head.data)
        self.assertEqual("c", linked_list.tail.data)

        linked_list.remove_node(last)
        self.assertEqual([], self._values(linked_list))
        self.assertIsNone(linked_list.head)
        self.assertIsNone(linked_list.tail)

    def test_move_to_front(self) -> None:
        """중간/끝 노드를 앞으로 옮겨 LRU 갱신에 필요한 재배치가 가능한지 확인한다."""
        linked_list = DoublyLinkedList()
        first = linked_list.insert_back("a")
        second = linked_list.insert_back("b")
        third = linked_list.insert_back("c")

        linked_list.move_to_front(third)
        self.assertEqual(["c", "a", "b"], self._values(linked_list))
        self.assertIs(linked_list.head, third)
        self.assertIs(linked_list.tail, second)

        linked_list.move_to_front(first)
        self.assertEqual(["a", "c", "b"], self._values(linked_list))
        self.assertIs(linked_list.head, first)

        linked_list.move_to_front(first)
        self.assertEqual(["a", "c", "b"], self._values(linked_list))

    def test_boundary_conditions_for_empty_and_singleton(self) -> None:
        """비어 있거나 원소 하나뿐인 경우에도 예외 없이 일관된 상태를 유지하는지 확인한다."""
        linked_list = DoublyLinkedList()

        self.assertIsNone(linked_list.remove_front())
        self.assertIsNone(linked_list.remove_back())

        lone = linked_list.insert_front("only")
        linked_list.move_to_front(lone)
        self.assertEqual(["only"], self._values(linked_list))

        linked_list.remove_node(lone)
        self.assertEqual([], self._values(linked_list))
        self.assertIsNone(linked_list.head)
        self.assertIsNone(linked_list.tail)


class HashMapCollisionKey:
    """충돌 상황을 강제로 만들기 위한 테스트 전용 키 객체."""

    def __init__(self, name: str) -> None:
        """식별용 이름을 저장한다."""
        self.name = name

    def __hash__(self) -> int:
        """모든 키가 같은 해시를 갖게 해 체이닝 경로를 강제한다."""
        return 1

    def __eq__(self, other: object) -> bool:
        """이름이 같을 때만 동일 키로 간주한다."""
        if not isinstance(other, HashMapCollisionKey):
            return False
        return self.name == other.name

    def __repr__(self) -> str:
        """실패 메시지에서 구분 가능한 표현을 제공한다."""
        return "HashMapCollisionKey(" + self.name + ")"


class HashMapTest(unittest.TestCase):
    """체이닝 해시맵의 충돌 처리와 확장 동작을 검증한다."""

    def test_hash_index_within_capacity(self) -> None:
        """해시 함수가 항상 현재 용량 범위 안의 인덱스를 반환하는지 확인한다."""
        hashmap = HashMap()

        for key in ["a", "abc", "user:1", "한글", "with spaces", "12345"]:
            index = hashmap._hash(key)
            self.assertGreaterEqual(index, 0)
            self.assertLess(index, hashmap._capacity)

    def test_chaining_collision_resolution(self) -> None:
        """동일 버킷 충돌이 발생해도 각 키를 독립적으로 저장/조회/삭제할 수 있어야 한다."""
        hashmap = HashMap()
        key1 = "a"
        key2 = "i"
        key3 = "q"
        self.assertEqual(hashmap._hash(key1), hashmap._hash(key2))
        self.assertEqual(hashmap._hash(key2), hashmap._hash(key3))

        hashmap.put(key1, "v1")
        hashmap.put(key2, "v2")
        hashmap.put(key3, "v3")

        self.assertEqual("v1", hashmap.get(key1))
        self.assertEqual("v2", hashmap.get(key2))
        self.assertEqual("v3", hashmap.get(key3))
        self.assertTrue(hashmap.contains(key1))
        self.assertTrue(hashmap.contains(key2))
        self.assertTrue(hashmap.contains(key3))
        self.assertEqual(3, hashmap.size())

        removed = hashmap.remove(key2)
        self.assertTrue(removed)
        self.assertIsNone(hashmap.get(key2))
        self.assertFalse(hashmap.contains(key2))
        self.assertEqual("v1", hashmap.get(key1))
        self.assertEqual("v3", hashmap.get(key3))
        self.assertEqual(2, hashmap.size())

    def test_resize_when_load_factor_exceeds_threshold(self) -> None:
        """8칸 기준 7번째 삽입에서 0.75 초과가 발생하면 16칸으로 늘어나야 한다."""
        hashmap = HashMap()

        self.assertEqual(8, hashmap._capacity)

        for i in range(7):
            hashmap.put("k" + str(i), "v" + str(i))

        self.assertEqual(16, hashmap._capacity)

        for i in range(7):
            self.assertEqual("v" + str(i), hashmap.get("k" + str(i)))

    def test_put_get_remove_contains_keys_size(self) -> None:
        """기본 공개 연산들이 계약된 결과를 반환하는지 확인한다."""
        hashmap = HashMap()

        hashmap.put("a", "1")
        hashmap.put("b", "2")
        hashmap.put("a", "3")

        self.assertEqual("3", hashmap.get("a"))
        self.assertEqual("2", hashmap.get("b"))
        self.assertIsNone(hashmap.get("missing"))
        self.assertTrue(hashmap.contains("a"))
        self.assertFalse(hashmap.contains("missing"))
        self.assertEqual(2, hashmap.size())

        keys = hashmap.keys()
        self.assertEqual(2, len(keys))
        self.assertIn("a", keys)
        self.assertIn("b", keys)

        removed = hashmap.remove("a")
        self.assertTrue(removed)
        self.assertFalse(hashmap.contains("a"))
        self.assertEqual(1, hashmap.size())
        self.assertFalse(hashmap.remove("a"))


class MinHeapTest(unittest.TestCase):
    """TTL 관리에 쓰이는 최소 힙의 우선순위 동작을 검증한다."""

    def test_push_pop_peek_size_and_order(self) -> None:
        """가장 이른 만료 시각이 항상 먼저 관찰되고 제거되어야 한다."""
        heap = MinHeap()

        self.assertEqual(0, heap.size())
        self.assertIsNone(heap.peek())
        self.assertIsNone(heap.pop())

        heap.push((30, "k3"))
        heap.push((10, "k1"))
        heap.push((20, "k2"))
        heap.push((10, "k1b"))

        self.assertEqual(4, heap.size())
        self.assertEqual((10, "k1"), heap.peek())

        popped = [heap.pop(), heap.pop(), heap.pop(), heap.pop()]
        self.assertEqual((10, "k1"), popped[0])
        self.assertEqual((10, "k1b"), popped[1])
        self.assertEqual((20, "k2"), popped[2])
        self.assertEqual((30, "k3"), popped[3])
        self.assertEqual(0, heap.size())
        self.assertIsNone(heap.pop())


class StringCommandsTest(unittest.TestCase):
    """문자열 기본 명령 6종의 CLI 출력 계약을 검증한다."""

    def test_string_commands_and_empty_keys_output(self) -> None:
        """SET/GET/DEL/EXISTS/DBSIZE/KEYS의 정상 경로와 빈 배열 출력을 확인한다."""
        store = MiniRedisStore()

        self.assertEqual("(integer) 0", run(store, "DBSIZE"))
        self.assertEqual("(empty array)", run(store, "KEYS"))
        self.assertEqual("(integer) 0", run(store, "EXISTS user:1"))
        self.assertEqual("(nil)", run(store, "GET user:1"))
        self.assertEqual("(integer) 0", run(store, "DEL user:1"))

        self.assertEqual("OK", run(store, 'SET user:1 "Alice Kim"'))
        self.assertEqual("OK", run(store, "SET user:2 Bob"))
        self.assertEqual('"Alice Kim"', run(store, "GET user:1"))
        self.assertEqual('"Bob"', run(store, "GET user:2"))
        self.assertEqual("(integer) 1", run(store, "EXISTS user:1"))
        self.assertEqual("(integer) 2", run(store, "DBSIZE"))

        keys_output = run(store, "KEYS")
        self.assertIn('1. "', keys_output)
        self.assertIn('"user:1"', keys_output)
        self.assertIn('"user:2"', keys_output)

        self.assertEqual("(integer) 1", run(store, "DEL user:1"))
        self.assertEqual("(integer) 0", run(store, "DEL user:1"))
        self.assertEqual("(nil)", run(store, "GET user:1"))
        self.assertEqual("(integer) 1", run(store, "DBSIZE"))


class MemoryAndLRUTest(unittest.TestCase):
    """메모리 제한, LRU 축출, OOM 처리 규칙을 검증한다."""

    def test_config_info_and_lru_eviction_example(self) -> None:
        """명세 예시와 동일한 수치로 축출 결과와 INFO memory를 확인한다."""
        store = MiniRedisStore()

        self.assertEqual("OK", run(store, "CONFIG SET maxmemory 30"))
        self.assertEqual("OK", run(store, "SET user:1 abcde"))
        self.assertEqual("OK", run(store, "SET user:2 abcde"))
        self.assertEqual("OK", run(store, "SET user:3 abcde"))

        self.assertEqual("(nil)", run(store, "GET user:1"))
        self.assertEqual('"abcde"', run(store, "GET user:2"))
        self.assertEqual('"abcde"', run(store, "GET user:3"))
        self.assertEqual("(integer) 2", run(store, "DBSIZE"))
        self.assertEqual(
            "used_memory:22\nmaxmemory:30\nevicted_keys:1",
            run(store, "INFO memory"),
        )

    def test_get_success_updates_lru_and_changes_eviction_target(self) -> None:
        """성공한 GET만 최근 사용으로 반영되어 다음 축출 대상이 바뀌어야 한다."""
        store = MiniRedisStore()

        self.assertEqual("OK", run(store, "CONFIG SET maxmemory 30"))
        self.assertEqual("OK", run(store, "SET user:1 abcde"))
        self.assertEqual("OK", run(store, "SET user:2 abcde"))
        self.assertEqual('"abcde"', run(store, "GET user:1"))
        self.assertEqual("OK", run(store, "SET user:3 abcde"))

        self.assertEqual('"abcde"', run(store, "GET user:1"))
        self.assertEqual("(nil)", run(store, "GET user:2"))
        self.assertEqual('"abcde"', run(store, "GET user:3"))
        self.assertEqual(
            "used_memory:22\nmaxmemory:30\nevicted_keys:1",
            run(store, "INFO memory"),
        )

    def test_single_entry_larger_than_maxmemory_returns_oom_and_is_not_stored(self) -> None:
        """단일 엔트리 자체가 제한보다 크면 축출 대신 즉시 OOM이어야 한다."""
        store = MiniRedisStore()

        self.assertEqual("OK", run(store, "CONFIG SET maxmemory 5"))
        result = run(store, "SET abc defghij")

        self.assertEqual("(error) OOM command not allowed when used_memory > 'maxmemory'", result)
        self.assertEqual("(integer) 0", run(store, "DBSIZE"))
        self.assertEqual("(nil)", run(store, "GET abc"))


class TTLTest(unittest.TestCase):
    """TTL과 만료 시의 부수 효과를 가짜 시계로 검증한다."""

    def test_expire_ttl_and_expired_get_does_not_revive_lru(self) -> None:
        """만료 전후 TTL 값과 만료 후 GET 결과가 계약대로 동작해야 한다."""
        clock = FakeClock(100.0)
        store = MiniRedisStore(now_fn=clock.now)

        self.assertEqual("OK", run(store, "SET keep alive"))
        self.assertEqual("(integer) 1", run(store, "EXPIRE keep 10"))
        self.assertEqual("(integer) 10", run(store, "TTL keep"))

        clock.advance(3)
        ttl_after_3 = run(store, "TTL keep")
        self.assertEqual("(integer) 7", ttl_after_3)

        clock.advance(8)
        self.assertEqual("(nil)", run(store, "GET keep"))
        self.assertEqual("(integer) 0", run(store, "EXISTS keep"))
        self.assertEqual("(integer) -2", run(store, "TTL keep"))

    def test_expired_get_leaves_lru_order_untouched(self) -> None:
        """만료된 키를 GET 해도 LRU 순서가 바뀌지 않고, 축출 대상도 그대로여야 한다."""
        clock = FakeClock()
        store = MiniRedisStore(now_fn=clock.now)

        self.assertEqual("OK", run(store, "SET old 1"))
        self.assertEqual("OK", run(store, "SET temp x"))
        self.assertEqual("(integer) 1", run(store, "EXPIRE temp 5"))
        self.assertEqual("OK", run(store, "SET new 2"))

        clock.advance(6)
        self.assertEqual("(nil)", run(store, "GET temp"))

        # 만료 키는 LRU 구조에서 사라지고, 나머지 순서(최근 -> 오래됨)는 그대로다.
        self.assertFalse(store._lru_nodes.contains("temp"))
        self.assertEqual(["new", "old"], list(store._lru_list))

        # 한도를 낮추면 여전히 가장 오래된 old 가 축출된다.
        self.assertEqual("OK", run(store, "CONFIG SET maxmemory 7"))
        self.assertEqual("(nil)", run(store, "GET old"))
        self.assertEqual('"2"', run(store, "GET new"))

    def test_ttl_minus_one_for_key_without_expiration(self) -> None:
        """만료 시간이 없는 키는 TTL이 -1이어야 한다."""
        clock = FakeClock()
        store = MiniRedisStore(now_fn=clock.now)

        self.assertEqual("OK", run(store, "SET plain value"))
        self.assertEqual("(integer) -1", run(store, "TTL plain"))

    def test_set_overwrite_clears_existing_ttl(self) -> None:
        """SET 덮어쓰기는 이전 TTL을 제거해 영속 키로 되돌려야 한다."""
        clock = FakeClock()
        store = MiniRedisStore(now_fn=clock.now)

        self.assertEqual("OK", run(store, "SET user value1"))
        self.assertEqual("(integer) 1", run(store, "EXPIRE user 20"))
        self.assertEqual("(integer) 20", run(store, "TTL user"))

        self.assertEqual("OK", run(store, "SET user value2"))
        self.assertEqual('"value2"', run(store, "GET user"))
        self.assertEqual("(integer) -1", run(store, "TTL user"))

    def test_expire_non_positive_deletes_immediately(self) -> None:
        """0 이하 TTL은 지연 없이 삭제되어야 이후 조회와 존재 확인이 일치한다."""
        clock = FakeClock()
        store = MiniRedisStore(now_fn=clock.now)

        self.assertEqual("OK", run(store, "SET temp value"))
        self.assertEqual("(integer) 1", run(store, "EXPIRE temp 0"))
        self.assertEqual("(nil)", run(store, "GET temp"))
        self.assertEqual("(integer) 0", run(store, "EXISTS temp"))
        self.assertEqual("(integer) -2", run(store, "TTL temp"))

        self.assertEqual("OK", run(store, "SET temp value"))
        self.assertEqual("(integer) 1", run(store, "EXPIRE temp -5"))
        self.assertEqual("(nil)", run(store, "GET temp"))
        self.assertEqual("(integer) -2", run(store, "TTL temp"))

    def test_del_removes_data_ttl_and_lru_together(self) -> None:
        """명시 삭제 뒤에는 데이터, TTL, LRU 참조가 함께 사라져야 한다."""
        clock = FakeClock()
        store = MiniRedisStore(now_fn=clock.now)

        self.assertEqual("OK", run(store, "SET a one"))
        self.assertEqual("(integer) 1", run(store, "EXPIRE a 100"))
        self.assertEqual("(integer) 1", run(store, "DEL a"))
        self.assertEqual("(nil)", run(store, "GET a"))
        self.assertEqual("(integer) 0", run(store, "EXISTS a"))
        self.assertEqual("(integer) -2", run(store, "TTL a"))
        self.assertEqual("(empty array)", run(store, "KEYS"))


class ErrorHandlingTest(unittest.TestCase):
    """표준 에러 문자열과 인자 검증 규칙을 확인한다."""

    def test_unknown_command(self) -> None:
        """알 수 없는 명령은 표준 unknown command 에러를 반환해야 한다."""
        store = MiniRedisStore()
        result = run(store, "NOPE")
        self.assertEqual("(error) ERR unknown command 'NOPE'", result)

    def test_wrong_number_of_arguments(self) -> None:
        """인자 개수가 맞지 않으면 wrong number of arguments 에러여야 한다."""
        store = MiniRedisStore()
        result = run(store, "GET")
        self.assertEqual("(error) ERR wrong number of arguments for 'GET' command", result)

    def test_value_is_not_an_integer_or_out_of_range(self) -> None:
        """정수 파싱 실패와 음수 메모리 제한은 동일한 표준 에러 형식을 따라야 한다."""
        store = MiniRedisStore()

        self.assertEqual(
            "(error) ERR value is not an integer or out of range",
            run(store, "EXPIRE key nope"),
        )
        self.assertEqual(
            "(error) ERR value is not an integer or out of range",
            run(store, "CONFIG SET maxmemory -1"),
        )

    def test_oom_error_message(self) -> None:
        """메모리 초과는 전용 OOM 메시지와 정확히 일치해야 한다."""
        store = MiniRedisStore()
        self.assertEqual("OK", run(store, "CONFIG SET maxmemory 3"))
        result = run(store, "SET ab cd")
        self.assertEqual("(error) OOM command not allowed when used_memory > 'maxmemory'", result)


class ParserTest(unittest.TestCase):
    """CLI 입력 해석이 값 보존에 실패하지 않는지 확인한다."""

    def test_tokenize_with_quotes(self) -> None:
        """따옴표 안 공백을 유지해 명령 계층의 값 파손을 막아야 한다."""
        self.assertEqual(["SET", "user:1", "Alice Kim"], tokenize('SET user:1 "Alice Kim"'))
        self.assertEqual(["GET", "user:1"], tokenize("GET user:1"))


class ReplIntegrationTest(unittest.TestCase):
    """실행 가능한 패키지 엔트리포인트의 stdin/stdout 통합 동작을 검증한다."""

    def test_python_m_mini_redis_repl(self) -> None:
        """서브프로세스 REPL이 여러 줄 입력을 순서대로 처리해야 실제 사용 시나리오가 안전하다."""
        input_data = "\n".join(
            [
                'SET user:1 "Alice Kim"',
                "GET user:1",
                "EXISTS user:1",
                "DBSIZE",
                "KEYS",
            ]
        ) + "\n"

        completed = subprocess.run(
            [sys.executable, "-m", "mini_redis"],
            input=input_data,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )

        self.assertEqual(0, completed.returncode, msg=completed.stderr)
        stdout = completed.stdout
        self.assertIn("OK", stdout)
        self.assertIn('"Alice Kim"', stdout)
        self.assertIn("(integer) 1", stdout)
        self.assertIn('1. "user:1"', stdout)


if __name__ == "__main__":
    unittest.main()
