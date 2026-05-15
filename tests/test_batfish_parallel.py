import threading
from src.validation.batfish_validator import BatfishValidator


def run_validation(thread_id):
    validator = BatfishValidator()
    # Simple valid config
    configs = {
        f"Router-{thread_id}": "interface GigabitEthernet0/1\n ip address 10.0.0.1 255.255.255.0\n"
    }
    print(f"Thread {thread_id} starting...")
    result = validator.validate(configs)
    print(f"Thread {thread_id} finished: {result['status']}")
    assert result["status"] == "PASS"


def test_parallel_batfish():
    threads = []
    for i in range(5):  # Run 5 validations in parallel
        t = threading.Thread(target=run_validation, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()
    print("✅ Parallel Batfish validation successful!")


if __name__ == "__main__":
    test_parallel_batfish()
