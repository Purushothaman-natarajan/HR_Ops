import requests
import time

BASE_URL = "http://localhost:8000"
TIMEOUT = 30

def test_endpoint(name, method, url, **kwargs):
    print(f"\nTesting {name}...")
    start = time.time()
    try:
        response = requests.request(method, url, timeout=TIMEOUT, **kwargs)
        elapsed = time.time() - start
        print(f"  Status: {response.status_code}")
        print(f"  Time: {elapsed:.3f}s")
        return elapsed
    except requests.exceptions.Timeout:
        print(f"  TIMEOUT after {TIMEOUT}s")
        return None
    except Exception as e:
        print(f"  ERROR: {e}")
        return None

def main():
    print("=" * 50)
    print("Latency Test for http://localhost:8000")
    print("=" * 50)

    # 1. Test /health
    test_endpoint("/health", "GET", f"{BASE_URL}/health")

    # 2. Test /graph/run
    test_endpoint(
        "/graph/run",
        "POST",
        f"{BASE_URL}/graph/run",
        json={"query": "Hello, how are you?"}
    )

    # 3. Test /conversation/start
    test_endpoint(
        "/conversation/start",
        "POST",
        f"{BASE_URL}/conversation/start",
        json={"query": "Hello, how are you?"}
    )

    print("\n" + "=" * 50)
    print("Test complete")
    print("=" * 50)

if __name__ == "__main__":
    main()