import 'dart:convert';

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../config/app_config.dart';

/// Handles all authentication API calls and local session persistence.
///
/// Token storage strategy:
///   Mobile (Android/iOS): flutter_secure_storage (encrypted keystore/keychain)
///   Web:                  SharedPreferences (no secure enclave — acceptable for
///                         web prototype, upgrade to HttpOnly cookies for production web)
///
/// Token lifecycle:
///   Access token  — JWT, short TTL (1 hour by default)
///   Refresh token — opaque, long TTL (7 days), stored securely
///   On access token expiry: auto-refresh using the refresh token
///   On refresh token expiry or revocation: force re-login
class AuthService {
  AuthService._();

  static const FlutterSecureStorage _secureStorage = FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
  );

  static const String _keyAccessToken  = 'auth_access_token';
  static const String _keyRefreshToken = 'auth_refresh_token';
  static const String _keyTokenExpiry  = 'auth_token_expiry_ms';
  static const String _keyUserName     = 'user_name';
  static const String _keyUserEmail    = 'user_email';
  static const String _keyUserRole     = 'user_role';
  static const String _keyLoggedIn     = 'is_logged_in';

  // ── Storage helpers ─────────────────────────────────────────────────────────

  static Future<void> _writeSecure(String key, String value) async {
    if (kIsWeb) {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(key, value);
    } else {
      await _secureStorage.write(key: key, value: value);
    }
  }

  static Future<String?> _readSecure(String key) async {
    if (kIsWeb) {
      final prefs = await SharedPreferences.getInstance();
      return prefs.getString(key);
    }
    return _secureStorage.read(key: key);
  }

  static Future<void> _deleteSecure(String key) async {
    if (kIsWeb) {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove(key);
    } else {
      await _secureStorage.delete(key: key);
    }
  }

  // ── API calls ───────────────────────────────────────────────────────────────

  /// Registers a new user. On success, immediately logs in to obtain tokens.
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

    if (response.statusCode == 409) {
      throw AuthException('An account with this email already exists.', 409);
    }
    if (response.statusCode != 201) {
      throw AuthException(_message(data, 'Registration failed.'), response.statusCode);
    }

    // Backend register returns UserResponse (no tokens).
    // Immediately login to obtain JWT + refresh token.
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

    if (response.statusCode == 429) {
      throw const AuthException(
          'Too many login attempts. Please wait a minute and try again.', 429);
    }
    if (response.statusCode != 200) {
      throw AuthException(_message(data, 'Login failed.'), response.statusCode);
    }

    return data;
  }

  /// Uses the stored refresh token to obtain a new access token.
  /// Returns true on success, false if refresh token is expired/revoked.
  static Future<bool> refreshAccessToken() async {
    final refreshToken = await _readSecure(_keyRefreshToken);
    if (refreshToken == null || refreshToken.isEmpty) return false;

    try {
      final response = await http
          .post(
            Uri.parse('${AppConfig.backendUrl}/auth/refresh'),
            headers: const {'Content-Type': 'application/json'},
            body: jsonEncode({'refresh_token': refreshToken}),
          )
          .timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = _decode(response);
        await _persistTokens(data);
        return true;
      }
    } catch (_) {}
    return false;
  }

  // ── Session persistence ─────────────────────────────────────────────────────

  /// Persists access token, refresh token, and user info from a TokenResponse.
  static Future<void> saveSession(Map<String, dynamic> data) async {
    final user    = data['user'] is Map ? Map<String, dynamic>.from(data['user'] as Map) : <String, dynamic>{};
    final accessT = data['access_token']?.toString();

    if (accessT == null || accessT.isEmpty) {
      throw const AuthException('Server returned no access token.', 200);
    }

    await _persistTokens(data);

    // Non-sensitive user metadata stored in SharedPreferences for quick access
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_keyUserName,  user['name']?.toString()  ?? '');
    await prefs.setString(_keyUserEmail, user['email']?.toString() ?? '');
    await prefs.setString(_keyUserRole,  user['role']?.toString()  ?? 'user');
    await prefs.setBool(_keyLoggedIn, true);
  }

  static Future<void> _persistTokens(Map<String, dynamic> data) async {
    final accessT   = data['access_token']?.toString();
    final refreshT  = data['refresh_token']?.toString();
    final expiresIn = data['expires_in'] as int? ?? 3600;

    if (accessT != null) {
      await _writeSecure(_keyAccessToken, accessT);
      final expiryMs = DateTime.now().millisecondsSinceEpoch + expiresIn * 1000;
      await _writeSecure(_keyTokenExpiry, expiryMs.toString());
    }
    if (refreshT != null) {
      await _writeSecure(_keyRefreshToken, refreshT);
    }
  }

  static Future<void> logout() async {
    // Notify backend to revoke the refresh token
    final refreshToken = await _readSecure(_keyRefreshToken);
    if (refreshToken != null && refreshToken.isNotEmpty) {
      try {
        await http
            .post(
              Uri.parse('${AppConfig.backendUrl}/auth/logout'),
              headers: const {'Content-Type': 'application/json'},
              body: jsonEncode({'refresh_token': refreshToken}),
            )
            .timeout(const Duration(seconds: 5));
      } catch (_) {
        // Best-effort — clear locally regardless
      }
    }

    await _deleteSecure(_keyAccessToken);
    await _deleteSecure(_keyRefreshToken);
    await _deleteSecure(_keyTokenExpiry);

    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_keyLoggedIn, false);
    await prefs.remove(_keyUserName);
    await prefs.remove(_keyUserEmail);
    await prefs.remove(_keyUserRole);
  }

  // ── Token access ────────────────────────────────────────────────────────────

  /// Returns a valid access token, refreshing it if expired.
  /// Returns null if the session is completely expired (force re-login).
  static Future<String?> getValidToken() async {
    final token  = await _readSecure(_keyAccessToken);
    final expiry = await _readSecure(_keyTokenExpiry);

    if (token == null || token.isEmpty) return null;

    // Check if access token is still valid (with 60s buffer)
    if (expiry != null) {
      final expiryMs = int.tryParse(expiry) ?? 0;
      final nowMs = DateTime.now().millisecondsSinceEpoch;
      if (nowMs < expiryMs - 60000) {
        return token; // Still valid
      }
    }

    // Try to refresh
    final refreshed = await refreshAccessToken();
    if (refreshed) {
      return _readSecure(_keyAccessToken);
    }

    return null; // Session expired — must re-login
  }

  /// Returns HTTP headers with a valid Bearer token, or empty headers if offline/expired.
  static Future<Map<String, String>> authHeaders() async {
    final token = await getValidToken();
    if (token == null) return const {'Content-Type': 'application/json'};
    return {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer $token',
    };
  }

  /// Returns true if the user has a valid (or refreshable) session.
  static Future<bool> isSessionValid() async {
    final token = await getValidToken();
    return token != null;
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

/// Typed auth exception with status code for structured error handling.
class AuthException implements Exception {
  final String message;
  final int statusCode;

  const AuthException(this.message, this.statusCode);

  bool get isUnauthorized => statusCode == 401;
  bool get isForbidden    => statusCode == 403;
  bool get isConflict     => statusCode == 409;
  bool get isRateLimited  => statusCode == 429;
  bool get isServerError  => statusCode >= 500;

  @override
  String toString() => message;
}
