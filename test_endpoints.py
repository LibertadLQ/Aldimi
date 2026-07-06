import time
import urllib.request

url_root = 'http://127.0.0.1:8000/'
url_pac = 'http://127.0.0.1:8000/pacientes'

for i in range(12):
    try:
        with urllib.request.urlopen(url_root, timeout=5) as r:
            print('ROOT:', r.status, r.read(200).decode('utf-8', errors='replace'))
        with urllib.request.urlopen(url_pac, timeout=5) as r:
            body = r.read().decode('utf-8', errors='replace')
            print('PACIENTES:', r.status, body[:1000])
        break
    except Exception as e:
        print('Attempt', i+1, 'failed:', e)
        time.sleep(1)
else:
    print('Server did not respond after retries')
