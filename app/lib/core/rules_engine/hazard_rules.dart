/// Deterministic hazard classification rules applied to GIS cell attributes.
/// All thresholds are transparent and documented — no black-box ML.
///
/// IMPORTANT: Output is always labeled "indicator, not prediction."
class HazardRules {
  HazardRules._();

  // ─── Thresholds (based on Chitral terrain study) ──────────────────────────
  static const double _slopeHighDeg = 30.0;   // > 30° → high landslide risk
  static const double _slopeMedDeg = 15.0;    // > 15° → medium landslide risk
  static const double _riverHighKm = 0.5;     // < 0.5 km → high flood risk
  static const double _riverMedKm = 1.5;      // < 1.5 km → medium flood risk

  /// Classify a hazard cell and return a [HazardAssessment].
  static HazardAssessment classify({
    required double slopeDeg,
    required double riverDistKm,
    required double elevationM,
  }) {
    final floodLevel = _classifyFlood(riverDistKm, elevationM);
    final landslideLevel = _classifyLandslide(slopeDeg, elevationM);
    final combined = _combine(floodLevel, landslideLevel);

    final factors = <String>[];
    if (riverDistKm < _riverHighKm) {
      factors.add('River distance < 0.5 km (high flood exposure)');
    } else if (riverDistKm < _riverMedKm) {
      factors.add('River distance < 1.5 km (moderate flood exposure)');
    }
    if (slopeDeg > _slopeHighDeg) {
      factors.add('Slope > 30° (high landslide susceptibility)');
    } else if (slopeDeg > _slopeMedDeg) {
      factors.add('Slope > 15° (moderate landslide susceptibility)');
    }
    if (elevationM < 1200) {
      factors.add('Low elevation increases flood water accumulation risk');
    }

    return HazardAssessment(
      overallLevel: combined,
      floodLevel: floodLevel,
      landslideLevel: landslideLevel,
      contributingFactors: factors,
      slopeDeg: slopeDeg,
      riverDistKm: riverDistKm,
      elevationM: elevationM,
    );
  }

  static HazardLevel _classifyFlood(double riverDistKm, double elevationM) {
    if (riverDistKm < _riverHighKm && elevationM < 2000) {
      return HazardLevel.high;
    }
    if (riverDistKm < _riverMedKm) return HazardLevel.medium;
    return HazardLevel.low;
  }

  static HazardLevel _classifyLandslide(
      double slopeDeg, double elevationM) {
    if (slopeDeg > _slopeHighDeg) return HazardLevel.high;
    if (slopeDeg > _slopeMedDeg) return HazardLevel.medium;
    return HazardLevel.low;
  }

  /// Worst-case combination — conservative for life-safety.
  static HazardLevel _combine(HazardLevel a, HazardLevel b) {
    if (a == HazardLevel.high || b == HazardLevel.high) {
      return HazardLevel.high;
    }
    if (a == HazardLevel.medium || b == HazardLevel.medium) {
      return HazardLevel.medium;
    }
    return HazardLevel.low;
  }
}

enum HazardLevel { high, medium, low, unknown }

extension HazardLevelExt on HazardLevel {
  String get label {
    switch (this) {
      case HazardLevel.high:
        return 'HIGH';
      case HazardLevel.medium:
        return 'MEDIUM';
      case HazardLevel.low:
        return 'LOW';
      case HazardLevel.unknown:
        return 'UNKNOWN';
    }
  }

  /// Hex color string for UI
  int get colorValue {
    switch (this) {
      case HazardLevel.high:
        return 0xFFD32F2F;
      case HazardLevel.medium:
        return 0xFFF57C00;
      case HazardLevel.low:
        return 0xFF388E3C;
      case HazardLevel.unknown:
        return 0xFF757575;
    }
  }
}

class HazardAssessment {
  final HazardLevel overallLevel;
  final HazardLevel floodLevel;
  final HazardLevel landslideLevel;
  final List<String> contributingFactors;
  final double slopeDeg;
  final double riverDistKm;
  final double elevationM;

  const HazardAssessment({
    required this.overallLevel,
    required this.floodLevel,
    required this.landslideLevel,
    required this.contributingFactors,
    required this.slopeDeg,
    required this.riverDistKm,
    required this.elevationM,
  });

  static const String disclaimer =
      'This is a coarse indicator based on slope & river proximity derived '
      'from DEM and OSM data. It is NOT a validated scientific prediction model '
      'and should not replace official NDMA/PDMA warnings.';
}
