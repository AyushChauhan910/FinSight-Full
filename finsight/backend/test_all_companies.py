import time
import requests

TICKERS = [
  'AAPL','MSFT','GOOGL','AMZN','NVDA','META','TSLA','BRK.B',
  'JPM','JNJ','V','UNH','XOM','LLY','AVGO','MA','HD','PG','MRK','ABBV'
]

URL_INGEST = 'http://127.0.0.1:8000/api/research/ingest'
URL_STATUS = 'http://127.0.0.1:8000/api/research/status/{}'

failed_tickers = []
successful_tickers = []

for ticker in TICKERS:
    print(f"\n=== Testing {ticker} ===")
    try:
        res = requests.post(URL_INGEST, json={"ticker": ticker, "years": 1})
        if res.status_code != 200:
            print(f"Failed to queue ingestion for {ticker}: {res.text}")
            failed_tickers.append(ticker)
            continue
            
        data = res.json()
        job_id = data.get('job_id')
        print(f"Queued job: {job_id}. Polling status...")
        
        while True:
            time.sleep(3)
            s_res = requests.get(URL_STATUS.format(job_id))
            if s_res.status_code != 200:
                print(f"Failed to fetch status: {s_res.text}")
                failed_tickers.append(ticker)
                break
                
            s_data = s_res.json()
            status = s_data.get('status')
            
            if status == 'completed':
                print(f"SUCCESS: {ticker} ingested successfully.")
                successful_tickers.append(ticker)
                break
            elif status == 'failed':
                print(f"ERROR: {ticker} ingestion failed. Reason: {s_data.get('error')}")
                failed_tickers.append(ticker)
                break
            else:
                progress = s_data.get('progress', '...')
                print(f"... {status} : {progress}")
                
    except Exception as e:
        print(f"Exception for {ticker}: {e}")
        failed_tickers.append(ticker)

print("\n\n=== SUMMARY ===")
print(f"Successful ({len(successful_tickers)}): {', '.join(successful_tickers)}")
print(f"Failed ({len(failed_tickers)}): {', '.join(failed_tickers)}")
