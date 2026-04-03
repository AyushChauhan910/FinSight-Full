import requests
import time
import json

BASE_URL = "http://127.0.0.1:8000"

def test_health():
    print("=== Testing Health ===")
    r = requests.get(f"{BASE_URL}/health", timeout=10)
    print(f"Status: {r.status_code}")
    print(f"Response: {r.text}")
    return r.status_code == 200

def test_companies():
    print("\n=== Testing Companies List ===")
    r = requests.get(f"{BASE_URL}/api/companies/", timeout=60)
    print(f"Status: {r.status_code}")
    data = r.json()
    print(f"Companies: {len(data.get('companies', []))}")
    for c in data.get('companies', []):
        print(f"  - {c['ticker']}: {c['document_count']} docs")
    return r.status_code == 200

def test_company_stats():
    print("\n=== Testing Company Stats ===")
    r = requests.get(f"{BASE_URL}/api/companies/NVDA/stats", timeout=60)
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"Ticker: {data['ticker']}")
        print(f"Documents: {data['document_count']}")
        print(f"Tokens: {data['total_tokens']}")
    return r.status_code == 200

def test_ingest():
    print("\n=== Testing Ingest ===")
    r = requests.post(f"{BASE_URL}/api/research/ingest", 
        json={"ticker": "AAPL", "years": 1}, timeout=30)
    print(f"Status: {r.status_code}")
    data = r.json()
    job_id = data.get("job_id")
    print(f"Job ID: {job_id}")
    print(f"Status: {data.get('status')}")
    
    if job_id:
        time.sleep(5)
        r2 = requests.get(f"{BASE_URL}/api/research/status/{job_id}", timeout=30)
        status_data = r2.json()
        print(f"Poll Status: {status_data.get('status')}")
        print(f"Progress: {status_data.get('progress')}")
    
    return r.status_code == 200

def test_query():
    print("\n=== Testing Query ===")
    print("This may take 1-3 minutes (4 LLM calls)...")
    start = time.time()
    try:
        r = requests.post(f"{BASE_URL}/api/research/query", 
            json={"ticker": "NVDA", "query": "What was total revenue?"},
            timeout=300)
        elapsed = time.time() - start
        print(f"Status: {r.status_code} in {elapsed:.1f}s")
        
        if r.status_code == 200:
            data = r.json()
            print(f"Iterations: {data.get('iterations_used')}")
            print(f"Tokens: {data.get('tokens_used')}")
            cites = data.get('citations', [])
            print(f"Citations: {len(cites)}")
            if cites:
                c0 = cites[0]
                print(f"  First citation keys: {list(c0.keys()) if isinstance(c0, dict) else type(c0)}")
            rep = data.get("report") or {}
            if isinstance(rep, dict):
                print(f"Report sections: {list(rep.keys())}")
            answer = data.get('answer', '')
            print(f"Answer preview: {answer[:300]}...")
        else:
            print(f"Error: {r.text[:500]}")
        return r.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_report():
    print("\n=== Testing Report ===")
    print("This may take 1-3 minutes...")
    start = time.time()
    try:
        r = requests.post(f"{BASE_URL}/api/research/report",
            json={"ticker": "NVDA"},
            timeout=300)
        elapsed = time.time() - start
        print(f"Status: {r.status_code} in {elapsed:.1f}s")
        
        if r.status_code == 200:
            data = r.json()
            print(f"Iterations: {data.get('iterations_used')}")
            rep = data.get('report') or {}
            if isinstance(rep, dict):
                es = (rep.get('executive_summary') or '')[:300]
                print(f"Report executive_summary preview: {es}...")
            else:
                print(f"Report preview: {str(rep)[:300]}...")
        return r.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_cors():
    print("\n=== Testing CORS ===")
    r = requests.options(f"{BASE_URL}/api/research/ingest",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        }, timeout=10)
    print(f"Status: {r.status_code}")
    print(f"Access-Control-Allow-Origin: {r.headers.get('access-control-allow-origin')}")
    return r.status_code in [200, 204]

if __name__ == "__main__":
    results = {}
    
    results["health"] = test_health()
    results["companies"] = test_companies()
    results["company_stats"] = test_company_stats()
    results["ingest"] = test_ingest()
    results["query"] = test_query()
    results["report"] = test_report()
    results["cors"] = test_cors()
    
    print("\n" + "="*50)
    print("SUMMARY")
    print("="*50)
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")
    
    all_passed = all(results.values())
    print(f"\nAll tests passed: {all_passed}")
