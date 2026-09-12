import 'package:flutter/foundation.dart';

/// Single source of truth for all runtime configuration.
///
/// Base URL selection:
///   Flutter Web (kIsWeb) → localhost (browser talks to local backend directly)
///   Android Emulator     → 10.0.2.2  (AVD special loopback for host machine)
///   Physical device      → set FLUTTER_BACKEND_URL env var at build time,
///                          or override [backendUrl] before app starts.
///
/// To override at build time:
///   flutter run --dart-define=BACKEND_URL=http://192.168.1.x:8000
class AppConfig {
  AppConfig._();

  // ── Backend URL ─────────────────────────────────────────────────────────────
  static const String _customUrl = String.fromEnvironment(
    'BACKEND_URL',
    defaultValue: '',
  );

  static String get backendUrl {
    if (_customUrl.isNotEmpty) return _customUrl;
    if (kIsWeb) return 'http://localhost:8002';
    // LAN backend for physical devices; override with BACKEND_URL when needed.
    return 'http://192.168.18.253:8002';
  }

  // ── Feature flags ───────────────────────────────────────────────────────────
  /// Set to false to disable all online sync and run fully offline.
  static const bool onlineSyncEnabled = true;

  // ── Package version ─────────────────────────────────────────────────────────
  static const String appVersion = '1.0.0';

  // ── Knowledge DB ───────────────────────────────────────────────────────────
  /// Version tag embedded in the bundled asset.
  /// Bump this when shipping a new offline_package build.
  static const int bundledDbVersion = 1;
}
