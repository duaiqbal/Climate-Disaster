import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../config/app_config.dart';

/// Handles all authentication API calls and local session persistence.
///
/// Token storage: SharedPreferences (acceptable for a demo/prototype).
/// Production upgrade path: swap to flutter_secure_storage.
class AuthService {
  AuthService._();

  // ── API calls ───────────────────────────────────────────────────────────────

  /// Registers a new user. Returns a [TokenResponse]-shaped map so
  /// [saveSession] can be called immediately (login-after-register flow).
  static Future<Map<String, dynamic>> register({
    required String name,
    required String email,
    required String password,
    String? district,
    String language = 'en',
  }) async {
    final response = await http
        .post(
          Uri.parse('${AppConfig.backendUrl}/auth/register'),
          headers: const {'Content-Type': 'application/json'},
          body: jsonEncode({
            'name': name.trim(),
            'email': email.trim(),
            'password': password,
            'district': district,
            'language': language,
          }),
        )
        .timeout(const Duration(seconds: 10));

    final data = _decode(response);

    if (response.statusCode != 201) {
      throw AuthException(
          _message(data, 'Registration failed.'), response.statusCode);
    }

    // Backend register returns UserResponse (no token).
    // Immediately login to obtain a token so the caller gets a TokenResponse.
    return login(email: email, password: password);
  }

  /// Logs in with email + password. Returns a TokenResponse map.
  static Future<Map<String, dynamic>> login({
    required String email,
    required String password,
  }) async {
    final response = await http
        .post(
          Uri.parse('${AppConfig.backendUrl}/auth/login'),
          headers: const {'Content-Type': 'application/json'},
          body: jsonEncode({
            'email': email.trim(),
            'password': password,
          }),
        )
        .timeout(const Duration(seconds: 10));

    final data = _decode(response);

    if (response.statusCode != 200) {
      throw AuthException(
          _message(data, 'Login failed.'), response.statusCode);
    }

    return data;
  }

  // ── Session persistence ─────────────────────────────────────────────────────

  /// Persists a [TokenResponse] map to SharedPreferences.
  static Future<void> saveSession(Map<String, dynamic> data) async {
    final prefs = await SharedPreferences.getInstance();
    final user = Map<String, dynamic>.from(
        data['user'] is Map ? data['user'] as Map : {});
    final token = data['access_token']?.toString();

    if (token == null || token.isEmpty) {
      throw const AuthException('Server returned no access token.', 200);
    }

    await prefs.setString('auth_token', token);
    await prefs.setString('user_name', user['name']?.toString() ?? '');
    await prefs.setString('user_email', user['email']?.toString() ?? '');

    final district = user['district']?.toString();
    if (district != null && district.isNotEmpty) {
      await prefs.setString('user_district', district);
    } else {
      await prefs.remove('user_district');
    }

    await prefs.setBool('is_logged_in', true);
    // Store token issue time for expiry detection (TTL = 24 h)
    await prefs.setInt(
        'token_issued_at', DateTime.now().millisecondsSinceEpoch);
  }

  static Future<void> logout() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('is_logged_in', false);
    await prefs.remove('auth_token');
    await prefs.remove('token_issued_at');
  }

  static Future<String?> getToken() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString('auth_token');
  }

  /// Returns true if a token exists and is within its 24-hour TTL.
  static Future<bool> isSessionValid() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('auth_token');
    if (token == null || token.isEmpty) return false;
    final issuedAt = prefs.getInt('token_issued_at');
    if (issuedAt == null) return false;
    final age = DateTime.now().millisecondsSinceEpoch - issuedAt;
    const ttlMs = 24 * 60 * 60 * 1000; // 24 h
    return age < ttlMs;
  }

  // ── Helpers ─────────────────────────────────────────────────────────────────

  static Map<String, dynamic> _decode(http.Response response) {
    try {
      final value = jsonDecode(response.body);
      return value is Map<String, dynamic> ? value : <String, dynamic>{};
    } catch (_) {
      return <String, dynamic>{};
    }
  }

  static String _message(Map<String, dynamic> data, String fallback) {
    final detail = data['detail'];
    return detail is String && detail.isNotEmpty ? detail : fallback;
  }
}

class AuthException implements Exception {
  final String message;
  final int statusCode;

  const AuthException(this.message, this.statusCode);

  @override
  String toString() => message;
}
