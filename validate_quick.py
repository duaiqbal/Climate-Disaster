import urllib.request, json, time

BASE = 'http://127.0.0.1:8002'

def get(path):
    r = urllib.request.urlopen(BASE + path, timeout=8)
    return json.loads(r.read()), r.status

def post(path, data):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(data).encode(),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    try:
        r = urllib.request.urlopen(req, timeout=8)
        return json.loads(r.read()), r.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode()), e.code

results = []

# Health
h, code = get('/health')
results.append(('GET /health', code == 200, h.get('status')))

# Alerts
a, code = get('/alerts')
results.append(('GET /alerts', code == 200, f"total={a.get('total')}"))

# Knowledge
m, code = get('/knowledge/meta')
results.append(('GET /knowledge/meta', code == 200, f"chunks={m.get('meta',{}).get('chunk_count','?')}"))

# Register
ts = int(time.time())
reg, code = post('/auth/register', {'name':'Test','email':f'v{ts}@t.com','password':'Test12345','language':'en'})
results.append(('POST /auth/register', code == 201, f"id={reg.get('id')}"))

# Login
login, code = post('/auth/login', {'email':f'v{ts}@t.com','password':'Test12345'})
results.append(('POST /auth/login', code == 200, 'token OK' if login.get('access_token') else 'NO TOKEN'))
results.append(('POST /auth/login refresh_token', bool(login.get('refresh_token')), ''))

# Bad login
bad, code = post('/auth/login', {'email':f'v{ts}@t.com','password':'WRONG'})
results.append(('POST /auth/login wrong pw', code == 401, ''))

# /auth/me
token = login.get('access_token','')
req = urllib.request.Request(BASE+'/auth/me', headers={'Authorization':f'Bearer {token}'})
try:
    r = urllib.request.urlopen(req, timeout=8)
    me = json.loads(r.read())
    results.append(('GET /auth/me', True, me.get('email','')))
except Exception as e:
    results.append(('GET /auth/me', False, str(e)))

passed = sum(1 for _,ok,_ in results if ok)
print(f'\n{"="*50}')
print(f'  Backend Validation — http://127.0.0.1:8002')
print(f'{"="*50}')
for name, ok, info in results:
    icon = 'PASS' if ok else 'FAIL'
    print(f'  {icon}  {name}  {info}')
print(f'\n  {passed}/{len(results)} passed')
print(f'{"="*50}\n')
