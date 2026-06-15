import requests, time
start = time.perf_counter()
r = requests.post('http://localhost:8000/graph/run', json={'query': 'What is compensation policy?'}, timeout=60)
print('Time:', time.perf_counter() - start)
print('Status:', r.status_code)
print(r.json())