import pathlib, re

root = pathlib.Path(r"c:\Users\Computer Arena\OneDrive\TOOBA INDUSTRY DOCUMENTS\disaster_dss")

checks = [
    ("bcrypt hashing",         "backend/core/security.py",         r"bcrypt\.hashpw|BCRYPT_ROUNDS"),
    ("JWT access tokens",      "backend/core/security.py",         r"jwt\.encode|HS256"),
    ("refresh token rotation", "backend/routers/auth.py",          r"revoked\s*=\s*True"),
    ("RefreshTokenORM",        "backend/routers/auth.py",          r"RefreshTokenORM"),
    ("flutter_secure_storage", "app/pubspec.yaml",                  r"flutter_secure_storage"),
    ("FlutterSecureStorage",   "app/lib/core/services/auth_service.dart", r"FlutterSecureStorage"),
    ("role-based admin check", "backend/routers/alerts.py",        r"require_admin|settings\.admin"),
    ("fail-fast production",   "backend/core/config.py",           r"sys\.exit|_validate_production"),
    ("test_auth.py exists",    "backend/tests/test_auth.py",       r"test_register|test_login"),
    ("invalid token test",     "backend/tests/test_auth.py",       r"invalid_token|malformed"),
    ("refresh test",           "backend/tests/test_auth.py",       r"test_refresh"),
]

all_ok = True
for name, rel, pattern in checks:
    path = root / rel
    if not path.exists():
        print(f"  FAIL  {name}: FILE NOT FOUND")
        all_ok = False
        continue
    text = path.read_text(encoding="utf-8", errors="replace")
    if re.search(pattern, text):
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name}: pattern '{pattern}' not found")
        all_ok = False

print()
print("RESULT:", "ALL PASS" if all_ok else "FAILURES DETECTED")
