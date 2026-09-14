class OfficialAlert {
  final String  id;
  final String  title;
  final String  sourceOrg;
  final String  severity;   // High, Moderate, Low
  final String  area;       // district or province
  final String  province;   // province field (Phase 2.3)
  final String  description;
  final String  issuedAgo;
  final String? aiRiskAssessment;
  final List<String> whatToDo;
  // Phase 2.3: "coordinate"|"district_name"|"province_only"|"national"|null
  final String? locationMatchType;

  const OfficialAlert({
    required this.id,
    required this.title,
    required this.sourceOrg,
    required this.severity,
    required this.area,
    this.province = '',
    required this.description,
    required this.issuedAgo,
    this.aiRiskAssessment,
    this.whatToDo = const [],
    this.locationMatchType,
  });

  String get source => sourceOrg;

  factory OfficialAlert.fromJson(Map<String, dynamic> json) {
    // Backend fields:  alert_id, body, district, issued_at, hazard_type
    // Flutter fields:  id,       description, area, issuedAgo, severity

    // Resolve id — backend uses alert_id
    final id = json['alert_id'] as String?
        ?? json['id'] as String?
        ?? 'alert_001';

    // Resolve description — backend uses body
    final description = json['body'] as String?
        ?? json['description'] as String?
        ?? 'No description available.';

    // Resolve area — backend uses district
    final area = json['district'] as String?
        ?? json['area'] as String?
        ?? 'Chitral District';

    // Resolve severity — backend returns HIGH/MEDIUM/LOW, UI expects High/Moderate/Low
    final rawSev = (json['severity'] as String? ?? 'HIGH').toUpperCase();
    final severity = rawSev == 'HIGH'
        ? 'High'
        : rawSev == 'MEDIUM' || rawSev == 'MODERATE'
            ? 'Moderate'
            : 'Low';

    // Resolve issuedAgo from issued_at timestamp
    String issuedAgo = json['issued_ago'] as String? ?? '';
    if (issuedAgo.isEmpty) {
      final rawDate = json['issued_at'] as String? ?? '';
      if (rawDate.isNotEmpty) {
        try {
          final issued = DateTime.parse(rawDate).toLocal();
          final diff   = DateTime.now().difference(issued);
          if (diff.inMinutes < 60) {
            issuedAgo = 'Issued ${diff.inMinutes} minutes ago';
          } else if (diff.inHours < 24) {
            issuedAgo = 'Issued ${diff.inHours} hours ago';
          } else {
            issuedAgo = 'Issued ${diff.inDays} days ago';
          }
        } catch (_) {
          issuedAgo = 'Recently issued';
        }
      } else {
        issuedAgo = 'Recently issued';
      }
    }

    // Derive aiRiskAssessment from hazard_type if not provided
    final hazardType = json['hazard_type'] as String? ?? '';
    final aiRisk = json['ai_risk_assessment'] as String?
        ?? _defaultAiAssessment(hazardType, area);

    return OfficialAlert(
      id          : id,
      title       : json['title'] as String? ?? 'Disaster Advisory',
      sourceOrg   : json['source_org'] as String?
                    ?? 'National Disaster Management Authority (NDMA)',
      severity    : severity,
      area        : area,
      province    : json['province'] as String? ?? '',
      description : description,
      issuedAgo   : issuedAgo,
      aiRiskAssessment: aiRisk,
      whatToDo    : (json['what_to_do'] as List<dynamic>?)
                      ?.map((e) => e.toString()).toList()
                    ?? _defaultWhatToDo(hazardType),
      locationMatchType: json['location_match_type'] as String?,
    );
  }

  static String _defaultAiAssessment(String hazardType, String area) {
    switch (hazardType.toLowerCase()) {
      case 'flash_flood':
      case 'flood':
        return 'Flash flood risk elevated in $area. '
            'River levels may rise rapidly. '
            'Avoid low-lying areas and riverbanks immediately.';
      case 'landslide':
        return 'Slope saturation increasing in $area due to prolonged rainfall. '
            'Avoid mountain roads and hillside areas.';
      case 'glof':
        return 'Glacial lake levels elevated in upper $area. '
            'Downstream communities should prepare for rapid water-level rise.';
      default:
        return 'Elevated hazard conditions detected in $area. '
            'Monitor NDMA and PDMA KP official channels for updates.';
    }
  }

  static List<String> _defaultWhatToDo(String hazardType) {
    switch (hazardType.toLowerCase()) {
      case 'flash_flood':
      case 'flood':
      case 'glof':
        return [
          'Move to higher ground immediately.',
          'Do not cross flowing water.',
          'Keep emergency kit and documents ready.',
          'Call Rescue 1122 if in danger.',
          'Monitor PDMA KP official updates.',
        ];
      case 'landslide':
        return [
          'Avoid unstable slopes and mountain roads.',
          'Stay away from hillsides during heavy rain.',
          'Prepare evacuation route to safe zone.',
          'Keep emergency kit ready.',
          'Monitor PDMA KP official updates.',
        ];
      default:
        return [
          'Monitor official updates.',
          'Keep essential documents and medicines ready.',
          'Avoid river channels and unstable slopes.',
          'Keep an evacuation route available.',
        ];
    }
  }

  static const OfficialAlert warningFromPMD = OfficialAlert(
    id: 'pmd_rain_01',
    title: 'Heavy Rainfall Advisory',
    sourceOrg: 'Pakistan Meteorological Department',
    severity: 'High',
    area: 'Chitral District',
    province: 'Khyber Pakhtunkhwa',
    description:
        'Heavy rainfall may increase flash-flood and landslide risk. Strong monsoon currents are expected to penetrate in upper parts of the country.',
    issuedAgo: 'Issued 2 hours ago',
    aiRiskAssessment:
        "Rainfall may increase slope saturation in your household's area. Slope stability index is currently at 42%.",
    whatToDo: [
      'Monitor official updates.',
      'Keep essential documents and medicines ready.',
      'Avoid river channels and unstable slopes.',
      'Keep an evacuation route available.',
      'Move livestock to a safer location if advised.',
    ],
    locationMatchType: 'district_name',
  );

  static const OfficialAlert watchFromNDMA = OfficialAlert(
    id: 'ndma_flood_02',
    title: 'Flash Flood Watch',
    sourceOrg: 'National Disaster Management Authority (NDMA)',
    severity: 'Moderate',
    area: 'Lowlying areas of Chitral',
    province: 'Khyber Pakhtunkhwa',
    description: 'Risk of flash flooding in local nullahs and streams due to expected rainfall.',
    issuedAgo: 'Issued 5 hours ago',
    aiRiskAssessment:
        'Local water levels may rise rapidly. Keep away from river embankments.',
    whatToDo: [
      'Stay away from waterways and low-lying ground.',
      'Prepare emergency go-bag.',
      'Identify nearest high ground shelter.',
    ],
    locationMatchType: 'district_name',
  );
}
