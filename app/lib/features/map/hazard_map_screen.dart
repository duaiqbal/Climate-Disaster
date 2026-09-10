import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import '../../core/local_db/database_helper.dart';
import '../../core/localization/app_localizations.dart';
import '../../core/rules_engine/hazard_rules.dart';
import '../../core/theme/app_theme.dart';

class HazardMapScreen extends StatefulWidget {
  const HazardMapScreen({super.key});

  @override
  State<HazardMapScreen> createState() => _HazardMapScreenState();
}

class _HazardMapScreenState extends State<HazardMapScreen> {
  _LocationState _state = _LocationState.idle;
  Position? _position;
  HazardAssessment? _assessment;
  Map<String, dynamic>? _rawCell;
  String? _errorMsg;

  @override
  void initState() {
    super.initState();
    _detectLocation();
  }

  Future<void> _detectLocation() async {
    setState(() {
      _state = _LocationState.detecting;
      _errorMsg = null;
    });

    try {
      // Permission check
      LocationPermission perm = await Geolocator.checkPermission();
      if (perm == LocationPermission.denied) {
        perm = await Geolocator.requestPermission();
      }
      if (perm == LocationPermission.deniedForever ||
          perm == LocationPermission.denied) {
        setState(() {
          _state = _LocationState.error;
          _errorMsg = 'Location permission denied.';
        });
        return;
      }

      final pos = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.medium,
      ).timeout(
        const Duration(seconds: 15),
        onTimeout: () => throw Exception('Location request timed out.'),
      );

      final cell = await DatabaseHelper.instance
          .getHazardCell(pos.latitude, pos.longitude);

      if (cell == null) {
        setState(() {
          _state = _LocationState.outOfArea;
          _position = pos;
        });
        return;
      }

      final assessment = HazardRules.classify(
        slopeDeg: (cell['slope_deg'] as num?)?.toDouble() ?? 0,
        riverDistKm: (cell['river_dist_km'] as num?)?.toDouble() ?? 99,
        elevationM: (cell['elevation_m'] as num?)?.toDouble() ?? 1000,
      );

      setState(() {
        _state = _LocationState.done;
        _position = pos;
        _rawCell = cell;
        _assessment = assessment;
      });
    } catch (e) {
      setState(() {
        _state = _LocationState.error;
        _errorMsg = e.toString();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);

    return Scaffold(
      appBar: AppBar(
        title: Text(loc.hazardMap),
        actions: [
          IconButton(
            icon: const Icon(Icons.my_location_rounded),
            tooltip: loc.myLocation,
            onPressed: _detectLocation,
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Status card
            _buildStatusCard(context, loc),
            const SizedBox(height: 16),

            // Assessment details
            if (_assessment != null) ...[
              _buildHazardDetailCard(context, loc),
              const SizedBox(height: 16),
              _buildFactorsCard(context),
              const SizedBox(height: 16),
              _buildRawDataCard(context),
              const SizedBox(height: 16),
            ],

            // Disclaimer
            _DisclaimerCard(text: loc.indicatorDisclaimer),
          ],
        ),
      ),
    );
  }

  Widget _buildStatusCard(BuildContext context, AppLocalizations loc) {
    if (_state == _LocationState.detecting) {
      return _InfoCard(
        icon: Icons.gps_fixed,
        iconColor: AppColors.primary,
        title: loc.detectingLocation,
        subtitle: 'Querying offline hazard gridâ€¦',
        trailing: const SizedBox(
          height: 20,
          width: 20,
          child: CircularProgressIndicator(
              strokeWidth: 2, color: AppColors.primary),
        ),
      );
    }

    if (_state == _LocationState.error) {
      return _InfoCard(
        icon: Icons.location_off_rounded,
        iconColor: AppColors.hazardHigh,
        title: loc.locationUnavailable,
        subtitle: _errorMsg ?? '',
        trailing: TextButton(
          onPressed: _detectLocation,
          child: Text(loc.retry),
        ),
      );
    }

    if (_state == _LocationState.outOfArea) {
      return _InfoCard(
        icon: Icons.location_searching_rounded,
        iconColor: AppColors.hazardMedium,
        title: 'Outside study area',
        subtitle:
            'Your location (${_position!.latitude.toStringAsFixed(4)}, '
            '${_position!.longitude.toStringAsFixed(4)}) is outside '
            'the Chitral hazard grid coverage.',
      );
    }

    if (_state == _LocationState.done && _assessment != null) {
      final level = _assessment!.overallLevel;
      return Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: Color(level.colorValue).withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: Color(level.colorValue).withValues(alpha: 0.4)),
        ),
        child: Column(
          children: [
            Row(
              children: [
                Container(
                  width: 56,
                  height: 56,
                  decoration: BoxDecoration(
                    color: Color(level.colorValue),
                    shape: BoxShape.circle,
                  ),
                  child: const Icon(Icons.location_on_rounded,
                      color: Colors.white, size: 28),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(loc.hazardLevel,
                          style: const TextStyle(
                              fontSize: 12, color: AppColors.textMuted)),
                      Text(
                        loc.hazardLevelLabel(level.label),
                        style: TextStyle(
                          fontSize: 26,
                          fontWeight: FontWeight.w800,
                          color: Color(level.colorValue),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                const Icon(Icons.gps_fixed,
                    size: 14, color: AppColors.textMuted),
                const SizedBox(width: 4),
                Text(
                  '${_position!.latitude.toStringAsFixed(5)}, '
                  '${_position!.longitude.toStringAsFixed(5)}',
                  style: const TextStyle(
                      fontSize: 12, color: AppColors.textMuted),
                ),
              ],
            ),
          ],
        ),
      );
    }

    // Idle
    return _InfoCard(
      icon: Icons.location_on_outlined,
      iconColor: AppColors.textMuted,
      title: loc.myLocation,
      subtitle: 'Tap the locate button to check your hazard level.',
    );
  }

  Widget _buildHazardDetailCard(
      BuildContext context, AppLocalizations loc) {
    final a = _assessment!;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Hazard Breakdown',
                style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 12),
            _HazardRow(
              icon: Icons.water_rounded,
              label: 'Flood',
              level: a.floodLevel,
            ),
            const SizedBox(height: 8),
            _HazardRow(
              icon: Icons.landslide_rounded,
              label: 'Landslide',
              level: a.landslideLevel,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFactorsCard(BuildContext context) {
    if (_assessment!.contributingFactors.isEmpty) return const SizedBox();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Contributing Factors',
                style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 10),
            ..._assessment!.contributingFactors.map(
              (f) => Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(Icons.circle, size: 6, color: AppColors.accent),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(f,
                          style: const TextStyle(
                              fontSize: 13, color: AppColors.textDark,
                              height: 1.4)),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildRawDataCard(BuildContext context) {
    if (_rawCell == null) return const SizedBox();
    final cell = _rawCell!;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Terrain Data',
                style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 10),
            _DataRow(
                label: 'Elevation',
                value:
                    '${(cell['elevation_m'] as num?)?.toStringAsFixed(0) ?? '?'} m'),
            _DataRow(
                label: 'Slope',
                value:
                    '${(cell['slope_deg'] as num?)?.toStringAsFixed(1) ?? '?'}Â°'),
            _DataRow(
                label: 'River distance',
                value:
                    '${(cell['river_dist_km'] as num?)?.toStringAsFixed(2) ?? '?'} km'),
          ],
        ),
      ),
    );
  }
}

enum _LocationState { idle, detecting, done, error, outOfArea }

class _InfoCard extends StatelessWidget {
  final IconData icon;
  final Color iconColor;
  final String title;
  final String subtitle;
  final Widget? trailing;

  const _InfoCard({
    required this.icon,
    required this.iconColor,
    required this.title,
    required this.subtitle,
    this.trailing,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        leading: Icon(icon, color: iconColor, size: 32),
        title: Text(title,
            style: const TextStyle(fontWeight: FontWeight.w600)),
        subtitle: Text(subtitle),
        trailing: trailing,
      ),
    );
  }
}

class _HazardRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final HazardLevel level;

  const _HazardRow({
    required this.icon,
    required this.label,
    required this.level,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, size: 20, color: Color(level.colorValue)),
        const SizedBox(width: 8),
        Text(label,
            style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w500)),
        const Spacer(),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
          decoration: BoxDecoration(
            color: Color(level.colorValue).withValues(alpha: 0.12),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Text(
            level.label,
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w700,
              color: Color(level.colorValue),
            ),
          ),
        ),
      ],
    );
  }
}

class _DataRow extends StatelessWidget {
  final String label;
  final String value;

  const _DataRow({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        children: [
          Text(label,
              style: const TextStyle(
                  fontSize: 13, color: AppColors.textMuted)),
          const Spacer(),
          Text(value,
              style: const TextStyle(
                  fontSize: 13, fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }
}

class _DisclaimerCard extends StatelessWidget {
  final String text;
  const _DisclaimerCard({required this.text});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.accent.withValues(alpha: 0.07),
        borderRadius: BorderRadius.circular(10),
        border:
            Border.all(color: AppColors.accent.withValues(alpha: 0.25)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.warning_amber_rounded,
              color: AppColors.accent, size: 18),
          const SizedBox(width: 8),
          Expanded(
            child: Text(text,
                style: const TextStyle(
                    fontSize: 12,
                    color: AppColors.textDark,
                    height: 1.5)),
          ),
        ],
      ),
    );
  }
}

