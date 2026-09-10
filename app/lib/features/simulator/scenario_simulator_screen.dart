import 'package:flutter/material.dart';
import '../../core/local_db/database_helper.dart';
import '../../core/retrieval/keyword_retriever.dart';
import '../../core/rules_engine/hazard_rules.dart';
import '../../core/theme/app_theme.dart';

/// Demo scenario simulator — walks through the three key demo scenarios
/// described in the README (airplane mode query, hazard check, online sync).
class ScenarioSimulatorScreen extends StatefulWidget {
  const ScenarioSimulatorScreen({super.key});

  @override
  State<ScenarioSimulatorScreen> createState() =>
      _ScenarioSimulatorScreenState();
}

class _ScenarioSimulatorScreenState
    extends State<ScenarioSimulatorScreen> {
  final KeywordRetriever _retriever = KeywordRetriever();
  int _activeScenario = 0;
  bool _running = false;
  String? _result;
  String? _metadata;

  final List<_Scenario> _scenarios = [
    _Scenario(
      title: 'Airplane Mode Query',
      subtitle:
          'Device offline — ask a flood safety question and retrieve verified offline answer.',
      icon: Icons.airplanemode_active_rounded,
      color: AppColors.primary,
      query: 'What should I do during a flood?',
      language: 'en',
    ),
    _Scenario(
      title: 'Hazard Indicator — Chitral Center',
      subtitle:
          'GPS-based lookup at Chitral coordinates against precomputed hazard grid.',
      icon: Icons.location_on_rounded,
      color: AppColors.hazardMedium,
      query: null,
      language: 'en',
      lat: 35.8511,
      lon: 71.7887,
    ),
    _Scenario(
      title: 'Roman Urdu Query',
      subtitle: 'Query in Roman Urdu — automatic spelling variant expansion.',
      icon: Icons.translate_rounded,
      color: AppColors.pdmaColor,
      query: 'Flood mein kya karein?',
      language: 'ru',
    ),
  ];

  Future<void> _runScenario(_Scenario s) async {
    setState(() {
      _running = true;
      _result = null;
      _metadata = null;
    });

    await Future.delayed(const Duration(milliseconds: 400));

    if (s.lat != null) {
      // Hazard scenario
      final cell = await DatabaseHelper.instance
          .getHazardCell(s.lat!, s.lon!);
      if (cell == null) {
        setState(() {
          _running = false;
          _result = 'No hazard cell found for coordinates.';
        });
        return;
      }
      final a = HazardRules.classify(
        slopeDeg: (cell['slope_deg'] as num?)?.toDouble() ?? 0,
        riverDistKm: (cell['river_dist_km'] as num?)?.toDouble() ?? 99,
        elevationM: (cell['elevation_m'] as num?)?.toDouble() ?? 1000,
      );
      setState(() {
        _running = false;
        _result = 'Overall hazard: ${a.overallLevel.label}\n'
            'Flood: ${a.floodLevel.label} | Landslide: ${a.landslideLevel.label}\n\n'
            'Factors:\n${a.contributingFactors.join('\n')}';
        _metadata = '⚠ ${HazardAssessment.disclaimer}';
      });
    } else {
      // Retrieval scenario
      final results = await _retriever.retrieve(
          query: s.query!, language: s.language, topK: 1);
      if (results.isEmpty) {
        setState(() {
          _running = false;
          _result = 'No results found for this query.';
        });
        return;
      }
      final r = results.first;
      setState(() {
        _running = false;
        _result = r.chunkText;
        _metadata =
            'Source: ${r.sourceOrg} · ${r.docTitle} · ${r.pubDate}\nEvidence: ${r.evidenceLevel}';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Demo Scenarios')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'These three scenarios demonstrate the core system capabilities as described in the README.',
              style: Theme.of(context)
                  .textTheme
                  .bodyMedium
                  ?.copyWith(color: AppColors.textMuted),
            ),
            const SizedBox(height: 16),

            // Scenario selector
            ..._scenarios.asMap().entries.map((e) {
              final i = e.key;
              final s = e.value;
              final isActive = _activeScenario == i;
              return GestureDetector(
                onTap: () => setState(() {
                  _activeScenario = i;
                  _result = null;
                  _metadata = null;
                }),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 200),
                  margin: const EdgeInsets.only(bottom: 8),
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: isActive
                        ? s.color.withValues(alpha: 0.08)
                        : Colors.white,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                      color: isActive
                          ? s.color
                          : Colors.grey.shade200,
                      width: isActive ? 2 : 1,
                    ),
                  ),
                  child: Row(
                    children: [
                      Icon(s.icon, color: s.color, size: 28),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(s.title,
                                style: TextStyle(
                                    fontWeight: FontWeight.w700,
                                    color: isActive ? s.color : AppColors.textDark,
                                    fontSize: 14)),
                            Text(s.subtitle,
                                style: const TextStyle(
                                    fontSize: 11,
                                    color: AppColors.textMuted,
                                    height: 1.4)),
                          ],
                        ),
                      ),
                      if (isActive)
                        Icon(Icons.chevron_right_rounded,
                            color: s.color),
                    ],
                  ),
                ),
              );
            }),

            const SizedBox(height: 16),

            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                icon: const Icon(Icons.play_arrow_rounded),
                label: Text(_running ? 'Running…' : 'Run Scenario'),
                onPressed: _running
                    ? null
                    : () => _runScenario(_scenarios[_activeScenario]),
              ),
            ),

            if (_running) ...[
              const SizedBox(height: 20),
              const Center(child: CircularProgressIndicator()),
            ],

            if (_result != null) ...[
              const SizedBox(height: 20),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                      color: AppColors.primaryLight.withValues(alpha: 0.3)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const Icon(Icons.article_outlined,
                            size: 16, color: AppColors.primary),
                        const SizedBox(width: 6),
                        Text('Result',
                            style: Theme.of(context)
                                .textTheme
                                .titleLarge
                                ?.copyWith(fontSize: 14)),
                      ],
                    ),
                    const SizedBox(height: 10),
                    Text(_result!,
                        style: const TextStyle(
                            fontSize: 13, height: 1.6)),
                    if (_metadata != null) ...[
                      const SizedBox(height: 12),
                      const Divider(height: 1),
                      const SizedBox(height: 8),
                      Text(_metadata!,
                          style: const TextStyle(
                              fontSize: 11,
                              color: AppColors.textMuted,
                              height: 1.5)),
                    ],
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _Scenario {
  final String title;
  final String subtitle;
  final IconData icon;
  final Color color;
  final String? query;
  final String language;
  final double? lat;
  final double? lon;

  const _Scenario({
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.color,
    required this.query,
    required this.language,
    this.lat,
    this.lon,
  });
}
