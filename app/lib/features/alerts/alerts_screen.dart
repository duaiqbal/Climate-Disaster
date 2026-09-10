import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../../core/config/app_config.dart';
import '../../core/local_db/database_helper.dart';
import '../../core/localization/app_localizations.dart';
import '../../core/providers/app_state_provider.dart';
import '../../core/theme/app_theme.dart';

class AlertsScreen extends StatefulWidget {
  const AlertsScreen({super.key});

  @override
  State<AlertsScreen> createState() => _AlertsScreenState();
}

class _AlertsScreenState extends State<AlertsScreen> {
  List<Map<String, dynamic>> _alerts = [];
  bool _loading = true;
  String? _error;
  bool _syncing = false;

  // Backend URL from shared config
  String get _backendUrl => AppConfig.backendUrl;

  @override
  void initState() {
    super.initState();
    _loadAlerts();
  }

  Future<void> _loadAlerts() async {
    setState(() { _loading = true; _error = null; });
    try {
      final rows = await DatabaseHelper.instance.getAlerts();
      setState(() {
        _alerts = List<Map<String, dynamic>>.from(rows);
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _loading = false;
        _error = e.toString();
      });
    }
  }

  Future<void> _syncAlerts() async {
    final appState = context.read<AppStateProvider>();
    if (!appState.isOnline) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('No internet connection. Showing cached alerts.'),
          backgroundColor: AppColors.hazardMedium,
        ),
      );
      return;
    }

    setState(() => _syncing = true);
    appState.setSyncing(true);

    try {
      final resp = await http
          .get(Uri.parse('$_backendUrl/alerts'))
          .timeout(const Duration(seconds: 10));

      if (resp.statusCode == 200) {
        // Backend returns AlertListResponse: {"total": N, "alerts": [...]}
        final decoded = jsonDecode(resp.body) as Map<String, dynamic>;
        final List<dynamic> data = decoded['alerts'] as List<dynamic>? ?? [];
        for (final item in data) {
          await DatabaseHelper.instance.upsertAlert({
            'alert_id': item['alert_id'],
            'title': item['title'],
            'body': item['body'],
            'hazard_type': item['hazard_type'],
            'severity': item['severity'],
            'issued_at': item['issued_at'],
            'source_org': item['source_org'],
            'district': item['district'],
          });
        }
        appState.setSyncSuccess();
        await _loadAlerts();
      } else {
        throw Exception('Server returned ${resp.statusCode}');
      }
    } catch (e) {
      appState.setSyncError(e.toString());
      setState(() => _syncing = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Sync failed: $e'),
            backgroundColor: AppColors.hazardHigh,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _syncing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);
    final appState = context.watch<AppStateProvider>();

    return Scaffold(
      appBar: AppBar(
        title: Text(loc.alerts),
        actions: [
          if (_syncing)
            const Padding(
              padding: EdgeInsets.only(right: 16),
              child: SizedBox(
                height: 20,
                width: 20,
                child: CircularProgressIndicator(
                    strokeWidth: 2, color: Colors.white),
              ),
            )
          else
            IconButton(
              icon: Icon(appState.isOnline
                  ? Icons.sync_rounded
                  : Icons.sync_disabled_rounded),
              tooltip: loc.syncNow,
              onPressed: _syncAlerts,
            ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? _ErrorBody(error: _error!, onRetry: _loadAlerts)
              : _alerts.isEmpty
                  ? _EmptyBody(message: loc.noAlerts)
                  : RefreshIndicator(
                      onRefresh: _syncAlerts,
                      child: ListView.builder(
                        padding: const EdgeInsets.symmetric(vertical: 8),
                        itemCount: _alerts.length,
                        itemBuilder: (_, i) =>
                            _AlertCard(alert: _alerts[i], loc: loc),
                      ),
                    ),
    );
  }
}

class _AlertCard extends StatelessWidget {
  final Map<String, dynamic> alert;
  final AppLocalizations loc;

  const _AlertCard({required this.alert, required this.loc});

  Color _severityColor(String? severity) {
    switch ((severity ?? '').toUpperCase()) {
      case 'RED':
      case 'EXTREME':
      case 'HIGH':
        return AppColors.hazardHigh;
      case 'ORANGE':
      case 'SEVERE':
      case 'MEDIUM':
        return AppColors.hazardMedium;
      default:
        return AppColors.hazardLow;
    }
  }

  IconData _hazardIcon(String? type) {
    switch ((type ?? '').toLowerCase()) {
      case 'flood':
        return Icons.water_rounded;
      case 'flash_flood':
        return Icons.thunderstorm_rounded;
      case 'landslide':
        return Icons.landslide_rounded;
      default:
        return Icons.warning_amber_rounded;
    }
  }

  @override
  Widget build(BuildContext context) {
    final severity = alert['severity']?.toString() ?? 'MEDIUM';
    final color = _severityColor(severity);

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header bar
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.1),
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(12),
                topRight: Radius.circular(12),
              ),
            ),
            child: Row(
              children: [
                Icon(_hazardIcon(alert['hazard_type']?.toString()),
                    color: color, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    alert['title']?.toString() ?? 'Alert',
                    style: TextStyle(
                      fontWeight: FontWeight.w700,
                      fontSize: 14,
                      color: color,
                    ),
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(
                    color: color,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Text(
                    severity,
                    style: const TextStyle(
                        color: Colors.white,
                        fontSize: 10,
                        fontWeight: FontWeight.w700),
                  ),
                ),
              ],
            ),
          ),

          // Body
          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  alert['body']?.toString() ?? '',
                  style: const TextStyle(
                      fontSize: 13, height: 1.5, color: AppColors.textDark),
                ),
                const SizedBox(height: 12),
                Wrap(
                  spacing: 6,
                  runSpacing: 4,
                  children: [
                    if (alert['source_org'] != null)
                      _Chip(
                          label: alert['source_org'].toString(),
                          icon: Icons.verified_outlined,
                          color: AppColors.ndmaColor),
                    if (alert['district'] != null)
                      _Chip(
                          label: alert['district'].toString(),
                          icon: Icons.place_outlined,
                          color: AppColors.textMuted),
                    if (alert['issued_at'] != null)
                      _Chip(
                          label: alert['issued_at'].toString().split('T').first,
                          icon: Icons.calendar_today_outlined,
                          color: AppColors.textMuted),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _Chip extends StatelessWidget {
  final String label;
  final IconData icon;
  final Color color;

  const _Chip(
      {required this.label, required this.icon, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 10, color: color),
          const SizedBox(width: 3),
          Text(label,
              style: TextStyle(
                  fontSize: 10,
                  color: color,
                  fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }
}

class _EmptyBody extends StatelessWidget {
  final String message;
  const _EmptyBody({required this.message});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.check_circle_outline_rounded,
              size: 64,
              color: AppColors.hazardLow.withValues(alpha: 0.5)),
          const SizedBox(height: 12),
          Text(message,
              style: const TextStyle(
                  color: AppColors.textMuted, fontSize: 14)),
        ],
      ),
    );
  }
}

class _ErrorBody extends StatelessWidget {
  final String error;
  final VoidCallback onRetry;

  const _ErrorBody({required this.error, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline_rounded,
                size: 48, color: AppColors.hazardHigh),
            const SizedBox(height: 12),
            Text(error,
                textAlign: TextAlign.center,
                style: const TextStyle(color: AppColors.textMuted)),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
              label: Text(AppLocalizations.of(context).retry),
            ),
          ],
        ),
      ),
    );
  }
}
