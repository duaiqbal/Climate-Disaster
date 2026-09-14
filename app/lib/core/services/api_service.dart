import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import '../config/app_config.dart';

class ApiException implements Exception {
  final int? statusCode;
  final String message;

  const ApiException(this.message, [this.statusCode]);

  @override
  String toString() => message;
}

class ApiResponse {
  final int statusCode;
  final dynamic body;

  const ApiResponse(this.statusCode, this.body);
}

/// HTTP wrapper connecting to the FastAPI backend.
/// URL is resolved from AppConfig so it works on Web (localhost) and Android emulator (10.0.2.2).
class ApiService {
  // Use web-safe URL on web, emulator loopback on Android
  static String get baseUrl {
    return AppConfig.backendUrl;
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
  static Future<dynamic> post(
      String endpoint, Map<String, dynamic> body) async {
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

  /// POST variant that preserves status and error details for user-facing flows.
  static Future<ApiResponse> postDetailed(
    String endpoint,
    Map<String, dynamic> body,
  ) async {
    try {
      final response = await http
          .post(
            Uri.parse('$baseUrl$endpoint'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode(body),
          )
          .timeout(timeoutDuration);
      return ApiResponse(response.statusCode, _decode(response.body));
    } on SocketException {
      throw const ApiException('Unable to connect to the server.');
    } on http.ClientException {
      throw const ApiException('Unable to connect to the server.');
    } catch (error) {
      if (error is ApiException) rethrow;
      throw const ApiException('The request could not be completed.');
    }
  }

  static dynamic _decode(String body) {
    try {
      return jsonDecode(body);
    } catch (_) {
      return null;
    }
  }
}
