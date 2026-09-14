// lib/core/services/alert_service.dart
//
// Real-time alert delivery with two layers:
//
//   Layer 1 — WebSocket (ws://localhost:8002/ws/alerts)
//     • Connects on first use, auto-reconnects on disconnect
//     • Server pushes every new alert instantly (zero polling delay)
//     • Heartbeat ping every 30s keeps the connection alive
//
//   Layer 2 — HTTP polling fallback (every 30 seconds)
//     • Activates only when WebSocket is disconnected
//     • Fetches GET /alerts, diffs against known alert IDs
//     • Pushes any truly-new alerts into the same stream
//
// Consumers:
//   final stream = AlertService.instance.alertStream;
//   stream.listen((alert) { ... });   // OfficialAlert objects, live
//
//   AlertService.instance.alerts       // current list (snapshot)
//   AlertService.instance.isConnected  // true = WS live

import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../models/official_alert.dart';
import 'api_service.dart';

class AlertService {
  AlertService._();
  static final AlertService instance = AlertService._();

  // ── Public state ────────────────────────────────────────────────────────────
  final List<OfficialAlert>          alerts       = [];
  final StreamController<OfficialAlert> _newAlertCtrl =
      StreamController<OfficialAlert>.broadcast();

  Stream<OfficialAlert> get alertStream  => _newAlertCtrl.stream;
  bool                  get isConnected  => _wsConnected;

  // ── Private state ───────────────────────────────────────────────────────────
  WebSocketChannel? _channel;
  bool              _wsConnected   = false;
  bool              _started       = false;
  Timer?            _reconnectTimer;
  Timer?            _pollTimer;
  final Set<String> _seenIds       = {};
  int               _reconnectDelay = 2; // seconds, doubles on each failure

  // ── Lifecycle ────────────────────────────────────────────────────────────────

  /// Call once (e.g. in DashboardScreen.initState or main()).
  void start() {
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

  // ── Initial HTTP load ────────────────────────────────────────────────────────

  Future<void> _loadInitialAlerts() async {
    try {
      final resp = await ApiService.get('/alerts?active_only=true&limit=50');
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

  // ── WebSocket connection ──────────────────────────────────────────────────────

  void _connectWs() {
    _reconnectTimer?.cancel();
    try {
      // Web uses ws://, same base host as HTTP backend
      final wsUrl = kIsWeb
          ? 'ws://localhost:8002/ws/alerts'
          : 'ws://10.0.2.2:8002/ws/alerts';

      _channel = WebSocketChannel.connect(Uri.parse(wsUrl));
      _channel!.stream.listen(
        _onWsMessage,
        onError:  (_) => _onWsDisconnected(),
        onDone:   ()  => _onWsDisconnected(),
        cancelOnError: false,
      );
      _wsConnected = true;
      _reconnectDelay = 2;          // reset backoff on success
      _stopPolling();               // WS is live — no need to poll
    } catch (_) {
      _onWsDisconnected();
    }
  }

  void _onWsDisconnected() {
    _wsConnected = false;
    _channel = null;
    _startPolling();                // fall back to HTTP polling
    // Exponential backoff reconnect (max 60s)
    _reconnectTimer = Timer(Duration(seconds: _reconnectDelay), _connectWs);
    _reconnectDelay = (_reconnectDelay * 2).clamp(2, 60);
  }

  // ── WebSocket message handler ─────────────────────────────────────────────────

  void _onWsMessage(dynamic raw) {
    try {
      final msg = jsonDecode(raw as String) as Map<String, dynamic>;
      final type = msg['type'] as String? ?? '';

      switch (type) {
        case 'new_alert':
          final alertJson = msg['alert'] as Map<String, dynamic>?;
          if (alertJson != null) {
            final alert = OfficialAlert.fromJson(alertJson);
            if (_seenIds.add(alert.id)) {
              alerts.insert(0, alert);
              _newAlertCtrl.add(alert);   // notify all listeners
            }
          }

        case 'monitor_done':
          // Server says monitor finished — re-fetch all alerts to get latest
          final newCount = msg['new_alerts'] as int? ?? 0;
          if (newCount > 0) _loadInitialAlerts();

        case 'ping':
          // Respond to server heartbeat — keeps connection alive
          _channel?.sink.add('{"type":"pong"}');

        default:
          break; // 'connected', 'pong' — no action needed
      }
    } catch (_) {}
  }

  // ── HTTP polling fallback (when WS is down) ───────────────────────────────────

  void _startPolling() {
    if (_pollTimer != null) return;
    _pollTimer = Timer.periodic(const Duration(seconds: 30), (_) => _pollAlerts());
  }

  void _stopPolling() {
    _pollTimer?.cancel();
    _pollTimer = null;
  }

  Future<void> _pollAlerts() async {
    if (_wsConnected) { _stopPolling(); return; }
    try {
      final resp = await ApiService.get('/alerts?active_only=true&limit=20');
      if (resp is Map<String, dynamic>) {
        final list = resp['alerts'] as List? ?? [];
        for (final raw in list) {
          final alert = OfficialAlert.fromJson(raw as Map<String, dynamic>);
          if (_seenIds.add(alert.id)) {
            alerts.insert(0, alert);
            _newAlertCtrl.add(alert);   // new alert found by polling
          }
        }
      }
    } catch (_) {}
  }

  // ── Manual refresh (pull-to-refresh) ─────────────────────────────────────────

  Future<List<OfficialAlert>> refresh() async {
    await _loadInitialAlerts();
    return List.unmodifiable(alerts);
  }
}
