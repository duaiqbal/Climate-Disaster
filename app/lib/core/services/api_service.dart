import 'dart:convert';
import 'dart:io';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:http/http.dart' as http;

/// HTTP wrapper connecting to the FastAPI backend.
/// URL is resolved from AppConfig so it works on Web (localhost) and Android emulator (10.0.2.2).
class ApiService {
  // Use web-safe URL on web, emulator loopback on Android
  static String get baseUrl {
    if (kIsWeb) return 'http://localhost:8002';
    return 'http://10.0.2.2:8002';
  }

  static const Duration timeoutDuration = Duration(seconds: 8);

  /// Helper to perform safe GET requests
  static Future<dynamic> get(String endpoint) async {
    try {
      final uri = Uri.parse('$baseUrl$endpoint');
      final response = await http.get(uri).timeout(timeoutDuration);
      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      }
      return null;
    } on SocketException {
      // Offline or backend unreachable
      return null;
    } catch (_) {
      return null;
    }
  }

  /// Helper to perform safe POST requests
  static Future<dynamic> post(String endpoint, Map<String, dynamic> body) async {
    try {
      final uri = Uri.parse('$baseUrl$endpoint');
      final response = await http
          .post(
            uri,
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode(body),
          )
          .timeout(timeoutDuration);
      if (response.statusCode == 200 || response.statusCode == 201) {
        return jsonDecode(response.body);
      }
      return null;
    } catch (_) {
      return null;
    }
  }
}
