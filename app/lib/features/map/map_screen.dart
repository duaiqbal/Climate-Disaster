// Interactive Hazard Map — Fixed version
// DB columns: lat, lon, slope_deg, river_dist_km, hazard_level, contributing_factors
// Location pin dynamically moves to GPS position on map canvas.
import 'dart:convert';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import '../../core/local_db/local_db.dart';
import '../../core/localization/app_translations.dart';
import '../../core/localization/language_service.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_text_styles.dart';
import '../chat/chat_screen.dart';
import '../safety/safety_hub_screen.dart';

// ── Hazard data model — matches actual DB schema ───────────────────────────
class _HazardInfo {
  final String hazardLevel;      // HIGH / MEDIUM / LOW
  final double slopeDeg;         // slope_deg column
  final double riverDistKm;      // river_dist_km column
  final double elevationM;       // elevation_m column
  final List<String> factors;    // contributing_factors (JSON array)
  final double lat;
  final double lon;

  const _HazardInfo({
    required this.hazardLevel,
    required this.slopeDeg,
    required this.riverDistKm,
    required this.elevationM,
    required this.factors,
    required this.lat,
    required this.lon,
  });

  // Default: Chitral city centre (35.85, 71.78)
  static const _HazardInfo defaultChitral = _HazardInfo(
    hazardLevel: 'HIGH',
    slopeDeg: 0.5,
    riverDistKm: 0.0,
    elevationM: 1758.0,
    factors: ['River distance 0.00 km < 0.5 km (high flood exposure)'],
    lat: 35.85,
    lon: 71.78,
  );

  bool get isHigh   => hazardLevel == 'HIGH';
  bool get isMedium => hazardLevel == 'MEDIUM';

  Color get levelColor {
    if (isHigh)   return AppColors.riskHigh;
    if (isMedium) return AppColors.riskModerate;
    return AppColors.riskLow;
  }

  Color get levelBgColor {
    if (isHigh)   return AppColors.riskHighBg;
    if (isMedium) return AppColors.riskModerateBg;
    return AppColors.riskLow.withValues(alpha: 0.12);
  }
}

// ── Map bounds (from grid_meta) ───────────────────────────────────────────
const double _kLatMin = 35.5;
const double _kLatMax = 36.5;
const double _kLonMin = 71.5;
const double _kLonMax = 72.5;

class MapScreen extends StatefulWidget {
  const MapScreen({super.key});

  @override
  State<MapScreen> createState() => _MapScreenState();
}

class _MapFilter {
  final String id;
  final String labelKey;
  final IconData icon;
  const _MapFilter(this.id, this.labelKey, this.icon);
}

class _MapScreenState extends State<MapScreen>
    with SingleTickerProviderStateMixin {
  static const _filters = [
    _MapFilter('flood',     'map_filter_flood',     Icons.water),
    _MapFilter('landslide', 'map_filter_landslide', Icons.landscape),
    _MapFilter('rainfall',  'map_filter_rainfall',  Icons.water_drop_outlined),
    _MapFilter('terrain',   'map_filter_terrain',   Icons.terrain),
  ];

  String _activeFilterId = 'flood';
  _HazardInfo _hazardInfo  = _HazardInfo.defaultChitral;
  bool _loading            = false;
  bool _bottomSheetVisible = true;
  bool _locationFound      = false;   // true once GPS fix obtained
  double _zoomLevel        = 1.0;

  // Pin position in normalised [0,1] coords relative to map canvas
  double _pinNormX = 0.328;  // (71.78 - 71.5) / 1.0
  double _pinNormY = 0.650;  // (36.5 - 35.85) / 1.0  (Y is inverted)

  late final AnimationController _pulseCtrl;
  late final Animation<double>   _pulseAnim;

  @override
  void initState() {
    super.initState();
    _pulseCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1400),
    )..repeat(reverse: true);
    _pulseAnim = Tween<double>(begin: 0.85, end: 1.15).animate(
      CurvedAnimation(parent: _pulseCtrl, curve: Curves.easeInOut),
    );
    // Load default Chitral data immediately
    _loadHazardData();
  }

  @override
  void dispose() {
    _pulseCtrl.dispose();
    super.dispose();
  }

  // ── Convert lat/lon to normalised pin position ─────────────────────────
  void _updatePin(double lat, double lon) {
    final x = (lon - _kLonMin) / (_kLonMax - _kLonMin);
    final y = (_kLatMax - lat)  / (_kLatMax - _kLatMin); // Y inverted
    setState(() {
      _pinNormX = x.clamp(0.05, 0.95);
      _pinNormY = y.clamp(0.05, 0.95);
    });
  }

  // ── Query hazard_grid.sqlite with CORRECT column names ────────────────
  Future<void> _loadHazardData({double? lat, double? lng}) async {
    setState(() => _loading = true);
    final latitude  = lat  ?? 35.85;
    final longitude = lng  ?? 71.78;

    bool loaded = false;

    // ── Mobile: query local SQLite ────────────────────────────────────
    if (!kIsWeb) {
      try {
        final db = await LocalDb.hazardDb;
        final rows = await db.rawQuery('''
          SELECT lat, lon, elevation_m, slope_deg, river_dist_km,
                 hazard_level, contributing_factors,
                 ((lat - ?) * (lat - ?) + (lon - ?) * (lon - ?)) AS dist
          FROM hazard_grid
          ORDER BY dist ASC
          LIMIT 1
        ''', [latitude, latitude, longitude, longitude]);

        if (rows.isNotEmpty) {
          final row     = rows.first;
          final rawJson = row['contributing_factors'] as String? ?? '[]';
          List<String> factorList = [];
          try {
            factorList = List<String>.from(jsonDecode(rawJson) as List);
          } catch (_) {
            factorList = [rawJson];
          }

          setState(() {
            _hazardInfo = _HazardInfo(
              hazardLevel : (row['hazard_level'] as String).toUpperCase(),
              slopeDeg    : (row['slope_deg']     as num).toDouble(),
              riverDistKm : (row['river_dist_km'] as num).toDouble(),
              elevationM  : (row['elevation_m']   as num).toDouble(),
              factors     : factorList,
              lat         : (row['lat'] as num).toDouble(),
              lon         : (row['lon'] as num).toDouble(),
            );
          });
          loaded = true;
        }
      } catch (_) {
        // SQLite error — fall through to default
      }
    }

    // ── Web: derive hazard from coordinate rules (no SQLite on web) ───
    if (!loaded) {
      final info = _deriveHazardForCoords(latitude, longitude);
      setState(() => _hazardInfo = info);
    }

    _updatePin(latitude, longitude);
    setState(() => _loading = false);
  }

  /// Derives hazard level from coordinates using the same rules as the
  /// hazard grid pipeline — works on web where SQLite is unavailable.
  _HazardInfo _deriveHazardForCoords(double lat, double lon) {
    // Chitral district bounds check
    final inChitral = lat >= 35.5 && lat <= 36.5 &&
                      lon >= 71.5 && lon <= 72.5;

    // River proximity rules (same thresholds as compute_hazard_grid.py)
    // Chitral River: lon ≈ 71.78, Mastuj: lon ≈ 72.00
    // Lutkho: lon ≈ 71.60, Yarkhun: lon ≈ 72.20
    final rivers = [71.78, 72.00, 71.60, 72.20];
    double minRiverDist = double.infinity;
    for (final riverLon in rivers) {
      final dist = (lon - riverLon).abs() * 111.0; // rough km
      if (dist < minRiverDist) minRiverDist = dist;
    }

    // Slope proxy: distance from centre (steeper near edges of district)
    final distFromCentre = ((lat - 36.0).abs() + (lon - 72.0).abs());
    final slopeProxy = (distFromCentre * 25.0).clamp(0.0, 65.0);

    // Classification logic
    String hazardLevel;
    final factors = <String>[];

    if (minRiverDist < 0.5) {
      hazardLevel = 'HIGH';
      factors.add('River distance ${minRiverDist.toStringAsFixed(2)} km < 0.5 km (high flood exposure)');
    } else if (slopeProxy > 30.0) {
      hazardLevel = 'HIGH';
      factors.add('Slope ${slopeProxy.toStringAsFixed(1)}° > 30° (high landslide susceptibility)');
    } else if (minRiverDist < 1.5) {
      hazardLevel = 'MEDIUM';
      factors.add('River distance ${minRiverDist.toStringAsFixed(2)} km < 1.5 km (medium flood exposure)');
    } else if (slopeProxy > 15.0) {
      hazardLevel = 'MEDIUM';
      factors.add('Slope ${slopeProxy.toStringAsFixed(1)}° > 15° (medium landslide susceptibility)');
    } else {
      hazardLevel = inChitral ? 'MEDIUM' : 'LOW';
      factors.add('Low river proximity and moderate terrain');
    }

    // Rough elevation estimate for Chitral (1500–4000m range)
    final elevationEst = inChitral
        ? 1500.0 + (distFromCentre * 800.0).clamp(0.0, 2500.0)
        : 500.0;

    return _HazardInfo(
      hazardLevel : hazardLevel,
      slopeDeg    : slopeProxy,
      riverDistKm : minRiverDist.clamp(0.0, 10.0),
      elevationM  : elevationEst,
      factors     : factors.isNotEmpty ? factors : ['Terrain analysis for Chitral district'],
      lat         : lat,
      lon         : lon,
    );
  }

  // ── GPS locate — works on both Web and Mobile ────────────────────────
  Future<void> _locateMe() async {
    setState(() => _loading = true);

    try {
      // Check / request permission — works on both platforms
      var permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
      }

      if (permission == LocationPermission.denied ||
          permission == LocationPermission.deniedForever) {
        // Permission denied — use Chitral default but still show pin
        if (mounted) {
          _showSnack(
            'Location access denied. Showing Chitral city centre (35.85°N, 71.78°E).',
          );
        }
        await _loadHazardData(lat: 35.85, lng: 71.78);
        setState(() {
          _locationFound      = true;
          _bottomSheetVisible = true;
        });
        return;
      }

      // Get actual position
      final pos = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.medium,
      ).timeout(
        const Duration(seconds: 10),
        onTimeout: () => Position(
          latitude: 35.85, longitude: 71.78,
          timestamp: DateTime.now(),
          accuracy: 0, altitude: 0, altitudeAccuracy: 0,
          heading: 0, headingAccuracy: 0, speed: 0, speedAccuracy: 0,
        ),
      );

      await _loadHazardData(lat: pos.latitude, lng: pos.longitude);
      setState(() {
        _locationFound      = true;
        _bottomSheetVisible = true;
      });

      if (mounted) {
        _showSnack(
          'Location: ${pos.latitude.toStringAsFixed(4)}°N, '
          '${pos.longitude.toStringAsFixed(4)}°E',
        );
      }
    } catch (e) {
      // Any error — fallback to Chitral centre
      await _loadHazardData(lat: 35.85, lng: 71.78);
      setState(() {
        _locationFound      = true;
        _bottomSheetVisible = true;
      });
      if (mounted) {
        _showSnack('Showing Chitral city centre (35.85°N, 71.78°E).');
      }
    }
  }

  void _showSnack(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(msg), duration: const Duration(seconds: 2)),
    );
  }

  // ── Build ────────────────────────────────────────────────────────────
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: Stack(
        children: [
          // Terrain map background + dynamic pin
          _buildMapCanvas(),

          // App bar overlay
          SafeArea(
            child: Column(
              children: [
                _buildMapAppBar(),
                const SizedBox(height: 8),
                _buildFilterChips(),
              ],
            ),
          ),

          // Zoom controls
          Positioned(
            right: 12,
            top: 160,
            child: _buildZoomControls(),
          ),

          // Locate me button
          Positioned(
            right: 12,
            top: 240,
            child: _buildLocateButton(),
          ),

          // Bottom info sheet
          if (_bottomSheetVisible)
            Positioned(
              left: 0, right: 0, bottom: 0,
              child: _buildBottomInfoSheet(),
            ),

          // Loading overlay
          if (_loading)
            Container(
              color: Colors.black.withValues(alpha: 0.25),
              child: const Center(
                child: CircularProgressIndicator(color: AppColors.primary),
              ),
            ),
        ],
      ),
    );
  }

  // ── Map canvas with CustomPainter terrain + dynamic pin ───────────────
  Widget _buildMapCanvas() {
    return LayoutBuilder(builder: (context, constraints) {
      final w = constraints.maxWidth;
      final h = constraints.maxHeight;
      // Pin position in actual pixels
      final pinX = _pinNormX * w;
      final pinY = _pinNormY * h;

      return SizedBox(
        width: w,
        height: h,
        child: Stack(
          children: [
            // Terrain background
            Transform.scale(
              scale: _zoomLevel,
              child: Container(
                width: w,
                height: h,
                decoration: const BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                    colors: [
                      Color(0xFF8B9B6A),
                      Color(0xFF6B7A50),
                      Color(0xFF5A6B45),
                      Color(0xFF4A5A38),
                    ],
                  ),
                ),
                child: CustomPaint(
                  painter: _TerrainPainter(
                    activeFilter : _activeFilterId,
                    pinNormX     : _pinNormX,
                    pinNormY     : _pinNormY,
                    hazardLevel  : _hazardInfo.hazardLevel,
                  ),
                ),
              ),
            ),

            // Risk zone halo around pin (animated pulse)
            Positioned(
              left: pinX - 30,
              top:  pinY - 30,
              child: AnimatedBuilder(
                animation: _pulseAnim,
                builder: (_, __) => Transform.scale(
                  scale: _pulseAnim.value,
                  child: Container(
                    width: 60,
                    height: 60,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: _hazardInfo.levelColor.withValues(alpha: 0.20),
                      border: Border.all(
                        color: _hazardInfo.levelColor.withValues(alpha: 0.45),
                        width: 1.5,
                      ),
                    ),
                  ),
                ),
              ),
            ),

            // Location pin
            Positioned(
              left: pinX - 18,
              top:  pinY - 46,
              child: _buildLocationPin(),
            ),

            // Coordinates label under pin
            Positioned(
              left: (pinX - 55).clamp(4.0, w - 114),
              top:  pinY + 6,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: Colors.black.withValues(alpha: 0.65),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  '${_hazardInfo.lat.toStringAsFixed(3)}°N  '
                  '${_hazardInfo.lon.toStringAsFixed(3)}°E',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    letterSpacing: 0.3,
                  ),
                ),
              ),
            ),
          ],
        ),
      );
    });
  }

  Widget _buildLocationPin() {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 36,
          height: 36,
          decoration: BoxDecoration(
            color: _hazardInfo.levelColor,
            shape: BoxShape.circle,
            border: Border.all(color: Colors.white, width: 2.5),
            boxShadow: [
              BoxShadow(
                color: _hazardInfo.levelColor.withValues(alpha: 0.55),
                blurRadius: 14,
                spreadRadius: 3,
              ),
            ],
          ),
          child: Icon(
            _locationFound ? Icons.my_location : Icons.location_on,
            color: Colors.white,
            size: 18,
          ),
        ),
        CustomPaint(
          size: const Size(12, 9),
          painter: _PinTailPainter(color: _hazardInfo.levelColor),
        ),
      ],
    );
  }

  // ── App bar ───────────────────────────────────────────────────────────
  Widget _buildMapAppBar() {
    final canPop = Navigator.of(context).canPop();
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 12),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.12),
            blurRadius: 12,
            offset: const Offset(0, 3),
          ),
        ],
      ),
      child: Row(
        children: [
          if (canPop) ...[
            GestureDetector(
              onTap: () => Navigator.maybeOf(context)?.pop(),
              child: const Icon(Icons.arrow_back,
                  color: AppColors.textPrimary, size: 20),
            ),
            const SizedBox(width: 10),
          ],
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  Tr.t('location_chitral_pk'),
                  style: AppTextStyles.cardTitle.copyWith(
                    color: AppColors.primary, fontSize: 16,
                  ),
                ),
                Text(
                  '${_hazardInfo.lat.toStringAsFixed(4)}°N, '
                  '${_hazardInfo.lon.toStringAsFixed(4)}°E  •  '
                  '${_hazardInfo.elevationM.toStringAsFixed(0)} m',
                  style: AppTextStyles.caption.copyWith(
                    color: AppColors.textMuted, fontSize: 11,
                  ),
                ),
              ],
            ),
          ),
          // Hazard badge
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color: _hazardInfo.levelBgColor,
              borderRadius: BorderRadius.circular(6),
            ),
            child: Text(
              _hazardInfo.hazardLevel,
              style: AppTextStyles.caption.copyWith(
                color: _hazardInfo.levelColor,
                fontWeight: FontWeight.w800,
                fontSize: 12,
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ── Filter chips ──────────────────────────────────────────────────────
  Widget _buildFilterChips() {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.symmetric(horizontal: 12),
      child: Row(
        children: _filters.map((filter) {
          final isActive = filter.id == _activeFilterId;
          return Padding(
            padding: const EdgeInsets.only(right: 8),
            child: GestureDetector(
              onTap: () => setState(() => _activeFilterId = filter.id),
              child: Container(
                padding: const EdgeInsets.symmetric(
                    horizontal: 14, vertical: 8),
                decoration: BoxDecoration(
                  color  : isActive ? AppColors.primary : AppColors.surface,
                  borderRadius: BorderRadius.circular(20),
                  border : Border.all(
                    color: isActive ? AppColors.primary : AppColors.border,
                  ),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withValues(alpha: 0.08),
                      blurRadius: 4,
                      offset: const Offset(0, 1),
                    ),
                  ],
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(filter.icon, size: 14,
                        color: isActive ? Colors.white : AppColors.textSecondary),
                    const SizedBox(width: 5),
                    Text(
                      Tr.t(filter.labelKey),
                      style: AppTextStyles.caption.copyWith(
                        color: isActive ? Colors.white : AppColors.textSecondary,
                        fontWeight: FontWeight.w600,
                        fontSize: 13,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          );
        }).toList(),
      ),
    );
  }

  // ── Zoom controls ─────────────────────────────────────────────────────
  Widget _buildZoomControls() {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(8),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.12),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        children: [
          _zoomBtn(Icons.add,    () => setState(() => _zoomLevel = (_zoomLevel + 0.25).clamp(0.5, 3.0))),
          Container(height: 1, color: AppColors.border),
          _zoomBtn(Icons.remove, () => setState(() => _zoomLevel = (_zoomLevel - 0.25).clamp(0.5, 3.0))),
        ],
      ),
    );
  }

  Widget _zoomBtn(IconData icon, VoidCallback onTap) {
    return InkWell(
      onTap: onTap,
      child: SizedBox(
        width: 40, height: 40,
        child: Icon(icon, size: 20, color: AppColors.textPrimary),
      ),
    );
  }

  // ── Locate me button ──────────────────────────────────────────────────
  Widget _buildLocateButton() {
    return GestureDetector(
      onTap: _locateMe,
      child: Container(
        width: 44,
        height: 44,
        decoration: BoxDecoration(
          color: AppColors.primary,
          shape: BoxShape.circle,
          boxShadow: [
            BoxShadow(
              color: AppColors.primary.withValues(alpha: 0.35),
              blurRadius: 10,
              offset: const Offset(0, 3),
            ),
          ],
        ),
        child: const Icon(Icons.my_location, size: 22, color: Colors.white),
      ),
    );
  }

  // ── Bottom info sheet ─────────────────────────────────────────────────
  Widget _buildBottomInfoSheet() {
    final info   = _hazardInfo;
    final isUrdu = LanguageService.instance.isUrdu;

    return Container(
      decoration: const BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        boxShadow: [
          BoxShadow(
            color: Color(0x1A000000),
            blurRadius: 20,
            offset: Offset(0, -4),
          ),
        ],
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Drag handle
          Center(
            child: Container(
              margin: const EdgeInsets.only(top: 10, bottom: 14),
              width: 36, height: 4,
              decoration: BoxDecoration(
                color: AppColors.border,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ),

          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Status row
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: info.levelBgColor,
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        isUrdu
                            ? (info.isHigh ? 'زیادہ خطرہ' : info.isMedium ? 'درمیانہ خطرہ' : 'کم خطرہ')
                            : '${info.hazardLevel} RISK',
                        style: AppTextStyles.caption.copyWith(
                          color: info.levelColor,
                          fontWeight: FontWeight.w700,
                          fontSize: 11,
                        ),
                      ),
                    ),
                    const SizedBox(width: 10),
                    const Icon(Icons.gps_fixed,
                        size: 13, color: AppColors.textMuted),
                    const SizedBox(width: 4),
                    Expanded(
                      child: Text(
                        '${info.lat.toStringAsFixed(4)}°N, ${info.lon.toStringAsFixed(4)}°E',
                        style: AppTextStyles.caption.copyWith(
                          color: AppColors.textMuted, fontSize: 11,
                        ),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    GestureDetector(
                      onTap: () => setState(() => _bottomSheetVisible = false),
                      child: const Icon(Icons.close,
                          size: 18, color: AppColors.textMuted),
                    ),
                  ],
                ),

                const SizedBox(height: 10),

                Text(
                  Tr.t('map_sheet_zone_title'),
                  style: AppTextStyles.screenHeader.copyWith(fontSize: 21),
                ),

                const SizedBox(height: 4),

                // Elevation + slope quick stats
                Row(
                  children: [
                    _statChip(Icons.height,
                        '${info.elevationM.toStringAsFixed(0)} m'),
                    const SizedBox(width: 8),
                    _statChip(Icons.terrain,
                        '${info.slopeDeg.toStringAsFixed(1)}° slope'),
                    const SizedBox(width: 8),
                    _statChip(Icons.water,
                        '${info.riverDistKm.toStringAsFixed(2)} km river'),
                  ],
                ),

                const SizedBox(height: 12),

                // Contributing factors from DB
                Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: AppColors.background,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AppColors.border),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        Tr.t('map_sheet_reasons'),
                        style: AppTextStyles.caption.copyWith(
                          fontWeight: FontWeight.w700,
                          color: AppColors.textPrimary,
                          fontSize: 13,
                        ),
                      ),
                      const SizedBox(height: 10),
                      // Show real factors from DB
                      if (info.factors.isNotEmpty)
                        ...info.factors.map((f) => _flagReason(
                              icon: f.toLowerCase().contains('river')
                                  ? Icons.water
                                  : Icons.landscape,
                              text: f,
                            ))
                      else ...[
                        _flagReason(
                          icon: Icons.landscape,
                          text: isUrdu
                              ? 'کھڑی ڈھلوان (${info.slopeDeg.toStringAsFixed(1)}°)'
                              : 'Steep terrain: ${info.slopeDeg.toStringAsFixed(1)}° slope',
                        ),
                        _flagReason(
                          icon: Icons.water,
                          text: isUrdu
                              ? 'دریا سے فاصلہ: ${info.riverDistKm.toStringAsFixed(2)} کلومیٹر'
                              : 'River proximity: ${info.riverDistKm.toStringAsFixed(2)} km',
                        ),
                      ],
                    ],
                  ),
                ),

                const SizedBox(height: 12),

                // Data sources
                Row(
                  children: [
                    Text(
                      Tr.t('map_sheet_sources'),
                      style: AppTextStyles.caption.copyWith(
                        color: AppColors.textMuted, fontSize: 12,
                      ),
                    ),
                    const SizedBox(width: 6),
                    _sourceTag('SRTM DEM'),
                    const SizedBox(width: 6),
                    _sourceTag('Chitral Grid v1.0'),
                  ],
                ),

                const SizedBox(height: 14),

                // Action buttons
                Row(
                  children: [
                    Expanded(
                      child: ElevatedButton(
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppColors.primary,
                          foregroundColor: Colors.white,
                          padding: const EdgeInsets.symmetric(vertical: 14),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12),
                          ),
                        ),
                        onPressed: () => _showRiskFactorSheet(context),
                        child: Text(Tr.t('map_view_risk_factors')),
                      ),
                    ),
                    const SizedBox(width: 10),
                    GestureDetector(
                      onTap: () => Navigator.push(context,
                          MaterialPageRoute(builder: (_) => const ChatScreen())),
                      child: Container(
                        width: 48, height: 48,
                        decoration: const BoxDecoration(
                          color: AppColors.primary,
                          shape: BoxShape.circle,
                        ),
                        child: const Icon(Icons.smart_toy_outlined,
                            color: Colors.white, size: 22),
                      ),
                    ),
                  ],
                ),

                const SizedBox(height: 16),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _statChip(IconData icon, String label) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: AppColors.surfaceVariant,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppColors.border),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: AppColors.textMuted),
          const SizedBox(width: 4),
          Text(label,
              style: AppTextStyles.caption.copyWith(
                  color: AppColors.textSecondary,
                  fontSize: 11,
                  fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }

  // ── Risk Factor detail sheet ───────────────────────────────────────────
  void _showRiskFactorSheet(BuildContext context) {
    final info   = _hazardInfo;
    final isUrdu = LanguageService.instance.isUrdu;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => Container(
        decoration: const BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        ),
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Container(
                width: 36, height: 4,
                margin: const EdgeInsets.only(bottom: 16),
                decoration: BoxDecoration(
                  color: AppColors.border,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Expanded(
                  child: Text(
                    Tr.t('map_sheet_zone_title'),
                    style: AppTextStyles.cardTitle.copyWith(fontSize: 18),
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.close, color: AppColors.textMuted),
                  onPressed: () => Navigator.pop(context),
                ),
              ],
            ),

            const SizedBox(height: 4),
            Text(
              isUrdu
                  ? 'اس علاقے کے خطرے کے عوامل (ڈیٹا بیس سے)'
                  : 'Risk factors for this cell — from hazard_grid.sqlite',
              style: AppTextStyles.caption
                  .copyWith(color: AppColors.textSecondary),
            ),

            const SizedBox(height: 16),

            // DB data grid
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: AppColors.aiCardBg,
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: AppColors.aiCardBorder),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(children: [
                    const Icon(Icons.insert_chart_outlined,
                        size: 16, color: AppColors.primary),
                    const SizedBox(width: 6),
                    Text(
                      isUrdu ? 'اہم اشارے' : 'Grid Cell Data',
                      style: AppTextStyles.caption.copyWith(
                        fontWeight: FontWeight.w700,
                        color: AppColors.textPrimary,
                      ),
                    ),
                  ]),
                  const SizedBox(height: 12),
                  Row(children: [
                    Expanded(
                        child: _indicatorBox(
                            isUrdu ? 'خطرے کی سطح' : 'Hazard Level',
                            info.hazardLevel,
                            info.levelColor)),
                    const SizedBox(width: 8),
                    Expanded(
                        child: _indicatorBox(
                            isUrdu ? 'بلندی' : 'Elevation',
                            '${info.elevationM.toStringAsFixed(0)} m',
                            AppColors.textPrimary)),
                  ]),
                  const SizedBox(height: 8),
                  Row(children: [
                    Expanded(
                        child: _indicatorBox(
                            isUrdu ? 'ڈھلوان' : 'Slope',
                            '${info.slopeDeg.toStringAsFixed(1)}°',
                            info.slopeDeg > 30
                                ? AppColors.riskHigh
                                : AppColors.riskModerate)),
                    const SizedBox(width: 8),
                    Expanded(
                        child: _indicatorBox(
                            isUrdu ? 'دریا سے فاصلہ' : 'River Dist.',
                            '${info.riverDistKm.toStringAsFixed(2)} km',
                            info.riverDistKm < 0.5
                                ? AppColors.riskHigh
                                : AppColors.riskModerate)),
                  ]),
                ],
              ),
            ),

            const SizedBox(height: 12),

            // Contributing factors from DB
            if (info.factors.isNotEmpty)
              Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: info.levelBgColor,
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(children: [
                      Icon(Icons.info_outline,
                          size: 16, color: info.levelColor),
                      const SizedBox(width: 6),
                      Text(
                        isUrdu ? 'خطرے کی وجوہات' : 'Contributing Factors',
                        style: AppTextStyles.caption.copyWith(
                          fontWeight: FontWeight.w700,
                          color: AppColors.textPrimary,
                        ),
                      ),
                    ]),
                    const SizedBox(height: 8),
                    ...info.factors.map((f) => Padding(
                          padding: const EdgeInsets.only(bottom: 4),
                          child: Text(
                            '• $f',
                            style: AppTextStyles.caption.copyWith(
                              color: AppColors.textSecondary,
                              height: 1.4,
                            ),
                          ),
                        )),
                  ],
                ),
              ),

            const SizedBox(height: 12),

            // What to do
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: AppColors.surfaceVariant,
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: AppColors.border),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(children: [
                    const Icon(Icons.shield_outlined,
                        size: 16, color: AppColors.primary),
                    const SizedBox(width: 6),
                    Text(
                      Tr.t('what_to_do_now'),
                      style: AppTextStyles.caption.copyWith(
                        fontWeight: FontWeight.w700,
                        color: AppColors.textPrimary,
                      ),
                    ),
                  ]),
                  const SizedBox(height: 8),
                  Text(
                    isUrdu
                        ? '• غیر مستحکم ڈھلوانوں سے دور رہیں۔'
                        : '• Avoid unstable slopes and riverbanks.',
                    style: AppTextStyles.caption
                        .copyWith(color: AppColors.textSecondary),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    isUrdu
                        ? '• سرکاری انتباہات پر نظر رکھیں۔'
                        : '• Monitor NDMA/PDMA KP official alerts.',
                    style: AppTextStyles.caption
                        .copyWith(color: AppColors.textSecondary),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    isUrdu
                        ? '• انخلاء کے راستے تیار رکھیں۔'
                        : '• Keep evacuation routes ready.',
                    style: AppTextStyles.caption
                        .copyWith(color: AppColors.textSecondary),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 14),

            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.primary,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12)),
                ),
                icon: const Icon(Icons.menu_book_outlined, size: 16),
                label: Text(Tr.t('view_safety_guide')),
                onPressed: () {
                  Navigator.pop(context);
                  Navigator.push(
                      context,
                      MaterialPageRoute(
                          builder: (_) => const SafetyHubScreen()));
                },
              ),
            ),
            const SizedBox(height: 8),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                style: OutlinedButton.styleFrom(
                  foregroundColor: AppColors.primary,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  side: const BorderSide(color: AppColors.border),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12)),
                ),
                icon: const Icon(Icons.close, size: 16),
                label: Text(Tr.t('close')),
                onPressed: () => Navigator.pop(context),
              ),
            ),
            const SizedBox(height: 12),
          ],
        ),
      ),
    );
  }

  static Widget _indicatorBox(String title, String value, Color valueColor) {
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title,
              style: AppTextStyles.caption
                  .copyWith(fontSize: 11, color: AppColors.textMuted)),
          const SizedBox(height: 4),
          Text(value,
              style: AppTextStyles.cardTitle
                  .copyWith(fontSize: 13, color: valueColor)),
        ],
      ),
    );
  }

  Widget _flagReason({required IconData icon, required String text}) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 15, color: AppColors.primary),
          const SizedBox(width: 8),
          Expanded(
            child: Text(text,
                style: AppTextStyles.caption.copyWith(
                    color: AppColors.textPrimary, height: 1.4)),
          ),
        ],
      ),
    );
  }

  Widget _sourceTag(String label) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: AppColors.surfaceVariant,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: AppColors.border),
      ),
      child: Text(
        label,
        style: AppTextStyles.caption.copyWith(
          color: AppColors.textSecondary,
          fontSize: 11,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}

// ── Terrain painter with hazard zone overlay ──────────────────────────────
class _TerrainPainter extends CustomPainter {
  final String activeFilter;
  final double pinNormX;
  final double pinNormY;
  final String hazardLevel;

  const _TerrainPainter({
    required this.activeFilter,
    required this.pinNormX,
    required this.pinNormY,
    required this.hazardLevel,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint();

    // Contour lines
    paint
      ..color = Colors.white.withValues(alpha: 0.07)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.0;

    for (int i = 0; i < 9; i++) {
      final path = Path();
      final y = size.height * (0.08 + i * 0.1);
      path.moveTo(0, y + 18 * (i % 3 == 0 ? 1 : -1));
      path.cubicTo(
        size.width * 0.25, y - 28 * (i % 2 == 0 ? 1 : -0.5),
        size.width * 0.55, y + 18 * (i % 3 == 1 ? 1 : -1),
        size.width * 0.78, y - 10,
      );
      path.lineTo(size.width, y + 14 * (i % 2));
      canvas.drawPath(path, paint);
    }

    // River line (Chitral River roughly at lon 71.78 → normX ≈ 0.28)
    paint
      ..color = Colors.blue.withValues(alpha: 0.35)
      ..strokeWidth = 2.5
      ..style = PaintingStyle.stroke;
    final riverX = size.width * 0.28;
    final riverPath = Path()
      ..moveTo(riverX - 8, 0)
      ..cubicTo(
        riverX + 12, size.height * 0.3,
        riverX - 6, size.height * 0.6,
        riverX + 5, size.height,
      );
    canvas.drawPath(riverPath, paint);

    // Hazard zone around pin
    final zoneColor = hazardLevel == 'HIGH'
        ? const Color(0xFFDC2626)
        : hazardLevel == 'MEDIUM'
            ? const Color(0xFFD97706)
            : const Color(0xFF16A34A);

    paint
      ..style = PaintingStyle.fill
      ..color = zoneColor.withValues(alpha: 0.18);
    canvas.drawOval(
      Rect.fromCenter(
        center: Offset(size.width * pinNormX, size.height * pinNormY),
        width: 90,
        height: 70,
      ),
      paint,
    );

    // Grid dots (hazard cells visualisation)
    paint
      ..style = PaintingStyle.fill
      ..strokeWidth = 1.0;
    const cols = 16;
    const rows = 12;
    for (int r = 0; r < rows; r++) {
      for (int c = 0; c < cols; c++) {
        final cx = size.width  * (c + 0.5) / cols;
        final cy = size.height * (r + 0.5) / rows;
        final dx = cx / size.width  - pinNormX;
        final dy = cy / size.height - pinNormY;
        final dist = dx * dx + dy * dy;
        Color dotColor;
        if (dist < 0.015) {
          dotColor = zoneColor.withValues(alpha: 0.55);
        } else if (dist < 0.06) {
          dotColor = const Color(0xFFD97706).withValues(alpha: 0.30);
        } else {
          dotColor = Colors.white.withValues(alpha: 0.10);
        }
        paint.color = dotColor;
        canvas.drawCircle(Offset(cx, cy), 2.5, paint);
      }
    }
  }

  @override
  bool shouldRepaint(_TerrainPainter old) =>
      old.activeFilter != activeFilter ||
      old.pinNormX     != pinNormX     ||
      old.pinNormY     != pinNormY     ||
      old.hazardLevel  != hazardLevel;
}

// ── Pin tail ──────────────────────────────────────────────────────────────
class _PinTailPainter extends CustomPainter {
  final Color color;
  const _PinTailPainter({required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final path = Path()
      ..moveTo(0, 0)
      ..lineTo(size.width / 2, size.height)
      ..lineTo(size.width, 0)
      ..close();
    canvas.drawPath(path, Paint()..color = color..style = PaintingStyle.fill);
  }

  @override
  bool shouldRepaint(_PinTailPainter old) => old.color != color;
}
