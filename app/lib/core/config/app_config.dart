import 'package:flutter/foundation.dart';

/// Single source of truth for all runtime configuration.
///
/// Backend URL priority order:
///   1. --dart-define=BACKEND_URL=https://... (build-time override — used for production)
///   2. kIsWeb → relative URL via localhost (local dev)
///   3. Android emulator → 10.0.2.2 (AVD loopback)
///   4. Physical device → LAN IP (local dev with USB)
///
/// Production build:
///   flutter build web --dart-define=BACKEND_URL=https://chitral-safe-backend.onrender.com
///
/// Local dev build:
///   flutter run -d chrome --web-port 8080
class AppConfig {
  AppConfig._();

  // ── Backend URL ─────────────────────────────────────────────────────────────
  /// Injected at build time via --dart-define=BACKEND_URL=https://...
  static const String _customUrl = String.fromEnvironment(
    'BACKEND_URL',
    defaultValue: '',
  );

  /// Production backend on Render.com
  static const String _productionUrl = 'https://chitral-safe-backend.onrender.com';

  static String get backendUrl {
    // 1. Build-time override (used for APK + production web builds)
    if (_customUrl.isNotEmpty) return _customUrl;

    // 2. Web: use production URL in release, localhost in debug
    if (kIsWeb) {
      // In release web build, use production backend
      return kReleaseMode ? _productionUrl : 'http://localhost:8002';
    }

    // 3. Android emulator
    // return 'http://10.0.2.2:8002';

    // 4. Physical device on LAN (change IP to your PC's WiFi IP)
    return 'http://192.168.100.42:8002';
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
