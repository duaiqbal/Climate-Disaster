"""
validate_backend.py — Live backend validation script.
Run from project root: python validate_backend.py
Backend must be running on port 8001.
"""
import urllib.request, json, sys, time

BASE = 'http://127.0.0.1:8001'
# Unique email per run avoids duplicate conflicts across validation runs
TEST_EMAIL = f'validate_{int(time.time())}@test.com'
passed = 0
failed = 0

def check(name, url, method='GET', data=None, expected_code=200):
    global passed, failed
    try:
        headers = {'Content-Type': 'application/json'} if data else {}
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        resp = urllib.request.urlopen(req, timeout=8)
        # Try JSON first, fall back to checking status code only (e.g. HTML pages)
        raw = resp.read()
        code = resp.status
        try:
            body = json.loads(raw)
        except Exception:
            body = {'_raw': raw[:40].decode(errors='replace')}
        if code == expected_code:
            print(f'  PASS  [{code}] {name}')
            passed += 1
            return body
        else:
            print(f'  FAIL  [{code}] {name}  (expected {expected_code})')
            failed += 1
            return body
    except urllib.error.HTTPError as e:
        body_raw = e.read().decode()[:120]
        if e.code == expected_code:
            print(f'  PASS  [{e.code}] {name}')
            passed += 1
            try:
                return json.loads(body_raw)
            except Exception:
                return {}
        else:
            print(f'  FAIL  [{e.code}] {name}  detail={body_raw}')
            failed += 1
            return {}
    except Exception as ex:
        print(f'  ERROR {name}: {ex}')
        failed += 1
        return {}


print('\n' + '='*55)
print('  Disaster DSS — Backend Live Validation')
print('  Target: ' + BASE)
print('='*55)

print('\n--- Core ---')
h = check('GET /health',  BASE + '/health')
if h.get('status') == 'ok':
    print(f'        version={h.get("version")}  db={h.get("db")}')
check('GET /',            BASE + '/')
check('GET /docs (swagger)', BASE + '/docs', expected_code=200)

print('\n--- Alerts ---')
alerts_resp = check('GET /alerts',           BASE + '/alerts')
if 'total' in alerts_resp:
    print(f'        total_alerts={alerts_resp["total"]}')
check('GET /alerts?district=Chitral', BASE + '/alerts?district=Chitral')

print('\n--- Knowledge ---')
meta = check('GET /knowledge/meta',   BASE + '/knowledge/meta')
if 'meta' in meta:
    m = meta['meta']
    print(f'        version={m.get("version", "n/a")}  chunks={m.get("chunk_count", "n/a")}')
check('GET /knowledge/chunks',        BASE + '/knowledge/chunks')
check('GET /knowledge/search?q=flood&language=en', BASE + '/knowledge/search?q=flood&language=en')

print('\n--- Sync ---')
check('GET /sync/status',             BASE + '/sync/status')

print('\n--- Authentication ---')
reg = check('POST /auth/register (new)',
            BASE + '/auth/register', 'POST',
            json.dumps({'name': 'Validation User',
                        'email': TEST_EMAIL,
                        'password': 'securepass99',
                        'language': 'en'}).encode(),
            expected_code=201)
if reg.get('id'):
    print(f'        registered user id={reg["id"]}  email={reg["email"]}')

login = check('POST /auth/login (valid)',
              BASE + '/auth/login', 'POST',
              json.dumps({'email': TEST_EMAIL,
                          'password': 'securepass99'}).encode(),
              expected_code=200)
tok = login.get('access_token', '')
if tok:
    print(f'        token={tok[:25]}...')

check('POST /auth/login (wrong password)',
      BASE + '/auth/login', 'POST',
      json.dumps({'email': TEST_EMAIL,
                  'password': 'WRONG'}).encode(),
      expected_code=401)

check('POST /auth/register (duplicate email)',
      BASE + '/auth/register', 'POST',
      json.dumps({'name': 'Dup User',
                  'email': TEST_EMAIL,
                  'password': 'securepass99',
                  'language': 'en'}).encode(),
      expected_code=409)

check('POST /auth/login (nonexistent user)',
      BASE + '/auth/login', 'POST',
      json.dumps({'email': 'nobody_exists@test.com',
                  'password': 'any'}).encode(),
      expected_code=401)

print('\n' + '='*55)
print(f'  TOTAL: {passed} passed  |  {failed} failed')
print('='*55 + '\n')

sys.exit(0 if failed == 0 else 1)
