// lib/core/services/alert_service.dart
//
// Real-time alert delivery with two layers:
//
//   Layer 1 — WebSocket (ws://localhost:8002/ws/alerts)
//     Instant push on every new alert; heartbeat ping every 30s.
//
//   Layer 2 — HTTP polling fallback (every 30 seconds)
//     Activates only when WebSocket is disconnected.
//
// Phase 2.3 — Location-aware fetching:
//   Alerts are fetched with the user's GPS coordinates when available,
//   passing ?lat=&lon=&radius_km=100 to the backend radius filter.
//   Falls back to province-name matching when GPS is unavailable.
//   Keeps a "show all Pakistan" toggle so users can see national alerts.
//
// location_match_type label values returned by backend:
//   "coordinate"    → alert is for user's exact area
//   "district_name" → alert matched user's district
//   "province_only" → alert matched user's province
//   "national"      → national-scope alert (Pakistan-wide)

import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../models/official_alert.dart';
import 'api_service.dart';

class AlertService {
  AlertService._();
  static final AlertService instance = AlertService._();

  // ── Public state ─────────────────────────────────────────────────────────────
  final List<OfficialAlert>             alerts      = [];
  final StreamController<OfficialAlert> _newAlertCtrl =
      StreamController<OfficialAlert>.broadcast();

  Stream<OfficialAlert> get alertStream => _newAlertCtrl.stream;
  bool get isConnected => _wsConnected;

  // Phase 2.3: current user location (set externally by map screen / GPS fix)
  double? _userLat;
  double? _userLon;
  String? _userProvince;
  String? _userDistrict;
  bool    _showAllPakistan = false; // national-view toggle

  /// Update the user's location so alerts are fetched for their area.
  /// [province] defaults to "Khyber Pakhtunkhwa" (app's primary scope).
  void setUserLocation({
    double? lat,
    double? lon,
    String? province = 'Khyber Pakhtunkhwa',
    String? district,
  }) {
    _userLat      = lat;
    _userLon      = lon;
    _userProvince = province;
    _userDistrict = district;
  }

  /// Toggle between "near me" and "all Pakistan" views.
  void setShowAllPakistan(bool value) {
    _showAllPakistan = value;
  }

  bool get showAllPakistan => _showAllPakistan;

  // ── Private state ─────────────────────────────────────────────────────────────
  WebSocketChannel? _channel;
  bool              _wsConnected    = false;
  bool              _started        = false;
  Timer?            _reconnectTimer;
  Timer?            _pollTimer;
  final Set<String> _seenIds        = {};
  int               _reconnectDelay = 2;

  // ── Lifecycle ──────────────────────────────────────────────────────────────────

  void start({double? lat, double? lon, String? province, String? district}) {
    if (lat != null || lon != null) {
      setUserLocation(lat: lat, lon: lon, province: province, district: district);
    }
    if (_started) return;
    _started = true;
    _loadInitialAlerts();
    _connectWs();
  }

  void dispose() {
    _channel?.sink.close();
    _reconnectTimer?.cancel();
    _pollTimer?.cancel();
    _newAlertCtrl.close();
    _started = false;
  }

  // ── URL builder ────────────────────────────────────────────────────────────────

  String _alertsUrl({int limit = 50}) {
    final params = <String, String>{'active_only': 'true', 'limit': '$limit'};

    if (!_showAllPakistan) {
      if (_userLat != null && _userLon != null) {
        // Radius-based: 100 km covers Chitral + surrounding areas comfortably
        params['lat']       = _userLat!.toStringAsFixed(5);
        params['lon']       = _userLon!.toStringAsFixed(5);
        params['radius_km'] = '100';
      } else if (_userProvince != null) {
        params['province'] = _userProvince!;
      } else if (_userDistrict != null) {
        params['district'] = _userDistrict!;
      }
      // If no location info at all, default to KP province
      if (!params.containsKey('lat') &&
          !params.containsKey('province') &&
          !params.containsKey('district')) {
        params['province'] = 'Khyber Pakhtunkhwa';
      }
    }
    // showAllPakistan = true → no location filter → backend returns everything

    final query = params.entries.map((e) => '${e.key}=${Uri.encodeComponent(e.value)}').join('&');
    return '/alerts?$query';
  }

  // ── Initial HTTP load ──────────────────────────────────────────────────────────

  Future<void> _loadInitialAlerts() async {
    try {
      final resp = await ApiService.get(_alertsUrl(limit: 50));
      if (resp is Map<String, dynamic>) {
        final list = resp['alerts'] as List? ?? [];
        for (final raw in list) {
          final alert = OfficialAlert.fromJson(raw as Map<String, dynamic>);
          if (_seenIds.add(alert.id)) {
            alerts.insert(0, alert);
          }
        }
      }
    } catch (_) {}
  }

  // ── WebSocket ──────────────────────────────────────────────────────────────────

  void _connectWs() {
    _reconnectTimer?.cancel();
    try {
      final wsUrl = kIsWeb
          ? 'ws://localhost:8002/ws/alerts'
          : 'ws://10.0.2.2:8002/ws/alerts';
      _channel = WebSocketChannel.connect(Uri.parse(wsUrl));
      _channel!.stream.listen(
        _onWsMessage,
        onError:       (_) => _onWsDisconnected(),
        onDone:        ()  => _onWsDisconnected(),
        cancelOnError: false,
      );
      _wsConnected    = true;
      _reconnectDelay = 2;
      _stopPolling();
    } catch (_) {
      _onWsDisconnected();
    }
  }

  void _onWsDisconnected() {
    _wsConnected = false;
    _channel     = null;
    _startPolling();
    _reconnectTimer = Timer(Duration(seconds: _reconnectDelay), _connectWs);
    _reconnectDelay = (_reconnectDelay * 2).clamp(2, 60);
  }

  void _onWsMessage(dynamic raw) {
    try {
      final msg  = jsonDecode(raw as String) as Map<String, dynamic>;
      final type = msg['type'] as String? ?? '';
      switch (type) {
        case 'new_alert':
          final j = msg['alert'] as Map<String, dynamic>?;
          if (j != null) {
            final alert = OfficialAlert.fromJson(j);
            if (_seenIds.add(alert.id)) {
              alerts.insert(0, alert);
              _newAlertCtrl.add(alert);
            }
          }
        case 'monitor_done':
          if ((msg['new_alerts'] as int? ?? 0) > 0) _loadInitialAlerts();
        case 'ping':
          _channel?.sink.add('{"type":"pong"}');
        default:
          break;
      }
    } catch (_) {}
  }

  // ── HTTP polling fallback ──────────────────────────────────────────────────────

  void _startPolling() {
    if (_pollTimer != null) return;
    _pollTimer = Timer.periodic(
        const Duration(seconds: 30), (_) => _pollAlerts());
  }

  void _stopPolling() {
    _pollTimer?.cancel();
    _pollTimer = null;
  }

  Future<void> _pollAlerts() async {
    if (_wsConnected) { _stopPolling(); return; }
    try {
      final resp = await ApiService.get(_alertsUrl(limit: 20));
      if (resp is Map<String, dynamic>) {
        final list = resp['alerts'] as List? ?? [];
        for (final raw in list) {
          final alert = OfficialAlert.fromJson(raw as Map<String, dynamic>);
          if (_seenIds.add(alert.id)) {
            alerts.insert(0, alert);
            _newAlertCtrl.add(alert);
          }
        }
      }
    } catch (_) {}
  }

  // ── Manual refresh (pull-to-refresh) ──────────────────────────────────────────

  Future<List<OfficialAlert>> refresh() async {
    alerts.clear();
    _seenIds.clear();
    await _loadInitialAlerts();
    return List.unmodifiable(alerts);
  }
}
