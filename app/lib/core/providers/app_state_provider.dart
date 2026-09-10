import 'package:flutter/material.dart';
import 'package:connectivity_plus/connectivity_plus.dart';

/// Global app-level state: connectivity, loading flags, sync status.
class AppStateProvider extends ChangeNotifier {
  bool _isOnline = false;
  bool _isSyncing = false;
  DateTime? _lastSyncedAt;
  String? _syncError;

  bool get isOnline => _isOnline;
  bool get isSyncing => _isSyncing;
  DateTime? get lastSyncedAt => _lastSyncedAt;
  String? get syncError => _syncError;

  AppStateProvider() {
    _monitorConnectivity();
  }

  void _monitorConnectivity() {
    Connectivity().onConnectivityChanged.listen((results) {
      final wasOnline = _isOnline;
      _isOnline = results.any((r) => r != ConnectivityResult.none);
      if (_isOnline != wasOnline) notifyListeners();
    });

    // Initial check
    Connectivity().checkConnectivity().then((results) {
      _isOnline = results.any((r) => r != ConnectivityResult.none);
      notifyListeners();
    });
  }

  void setSyncing(bool value) {
    _isSyncing = value;
    notifyListeners();
  }

  void setSyncSuccess() {
    _isSyncing = false;
    _lastSyncedAt = DateTime.now();
    _syncError = null;
    notifyListeners();
  }

  void setSyncError(String message) {
    _isSyncing = false;
    _syncError = message;
    notifyListeners();
  }
}
