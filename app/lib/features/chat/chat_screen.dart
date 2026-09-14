import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import '../../core/retrieval/retrieval_engine.dart';
import '../../core/rules_engine/rules_engine.dart';
import '../../core/services/api_service.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_text_styles.dart';
import '../../core/localization/app_translations.dart';
import '../../core/localization/language_service.dart';

class _ChatMessage {
  final String text;
  final bool isUser;
  final List<String> recommendedSteps;
  final List<String> sources;
  final String? evidenceLevel;
  bool xaiExpanded = false;

  _ChatMessage({
    required this.text,
    required this.isUser,
    this.recommendedSteps = const [],
    this.sources = const [],
    this.evidenceLevel,
  });
}

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final TextEditingController _controller = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final List<_ChatMessage> _messages = [];
  bool _loading = false;
  bool _isOnline = false;

  List<String> get _suggestionChips => [
    Tr.t('chip_why_risk'),
    Tr.t('chip_heavy_rain'),
    Tr.t('chip_what_pack'),
    Tr.t('chip_alert_mean'),
  ];

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  Future<void> _submitQuery(String queryText) async {
    final query = queryText.trim();
    if (query.isEmpty) return;

    setState(() {
      _messages.add(_ChatMessage(text: query, isUser: true));
      _loading = true;
    });
    _controller.clear();
    _scrollToBottom();

    String answerText;
    List<String> steps = [];
    List<String> sources = [];
    String? evidenceLabel;

    // Try backend first (with timeout)
    // Send user's actual selected language
    final lang = LanguageService.instance.isUrdu
        ? 'ur'
        : LanguageService.instance.isRomanUrdu
            ? 'ru'
            : 'en';

    final apiResponse = await ApiService.post(
      '/rag/query',
      {'question': query, 'language': lang, 'top_k': 5},
    );

    if (apiResponse != null &&
        apiResponse['answer'] != null &&
        apiResponse['confidence'] != 'insufficient') {
      // -- Backend success ----------------------------------------------
      _isOnline = true;
      answerText = apiResponse['answer'] as String;
      if (apiResponse['sources'] is List) {
        sources = List<String>.from(
          (apiResponse['sources'] as List).map((s) {
            final org   = (s['source_org'] ?? '').toString();
            final title = (s['doc_title']  ?? '').toString();
            final url   = (s['source_url'] ?? '').toString();
            if (url.isNotEmpty) {
              return '$org — $title\n$url';
            }
            return '$org — $title';
          }),
        );
      }
      evidenceLabel = Tr.t('evidence_high');
    } else {
      // -- Offline / backend unreachable --------------------------------
      _isOnline = false;

      if (!kIsWeb) {
        // Mobile: local SQLite retrieval
        final chunks = await RetrievalEngine.search(query);
        final response =
            RulesEngine.buildResponse(query, chunks, offline: true);
        answerText = response.answerText;
        evidenceLabel = _evidenceLabel(response.evidenceLevel);
        sources = response.sources
            .map((s) => '${s.sourceOrg}: ${s.sourceTitle}')
            .toList();
      } else {
        // Web: smart keyword-based fallback answer
        answerText = _getOfflineFallback(query);
        evidenceLabel = Tr.t('evidence_limited');
        sources = ['NDMA: Official Disaster Guidelines',
                   'PDMA KP: Flood Preparedness'];
      }

      steps = [
        Tr.t('offline_step_1'),
        Tr.t('offline_step_2'),
        Tr.t('offline_step_3'),
        Tr.t('offline_step_4'),
      ];
    }

    setState(() {
      _messages.add(_ChatMessage(
        text: answerText,
        isUser: false,
        recommendedSteps: steps,
        sources: sources,
        evidenceLevel: evidenceLabel,
      ));
      _loading = false;
    });
    _scrollToBottom();
  }

  /// Returns a query-specific offline answer — every query gets a DIFFERENT response.
  /// Matches backend rag_service.py logic exactly so offline = online quality.
  String _getOfflineFallback(String query) {
    final q    = query.toLowerCase();
    final isUr = LanguageService.instance.isUrdu;
    final isRu = LanguageService.instance.isRomanUrdu;

    // -- Normalize Urdu/Roman Urdu keywords ----------------------------------
    final qn = q
        .replaceAll('?????',     'flood')
        .replaceAll('????',      'rain')
        .replaceAll('?????',     'earthquake')
        .replaceAll('???? ??????', 'landslide')
        .replaceAll('??????',   'emergency')
        .replaceAll('?????',     'contact')
        .replaceAll('???',       'bag')
        .replaceAll('selab',     'flood')
        .replaceAll('sailaab',   'flood')
        .replaceAll('seelab',    'flood')
        .replaceAll('baarish',   'rain')
        .replaceAll('barish',    'rain')
        .replaceAll('zalzala',   'earthquake')
        .replaceAll('bhukamp',   'earthquake')
        .replaceAll('tayyari',   'prepare');

    // -- GLOF (specific — check before flood) --------------------------------
    if (qn.contains('glof') || qn.contains('glacial') ||
        qn.contains('yarkhun') || qn.contains('glacier')) {
      if (isUr) return 'GLOF (?????? ???? ?? ?????) — ?????:\n\n'
          '• ????? ??? 53 ?????? ?????? ?????? ???\n'
          '• ?????? ?????? ?????? ???? ????? ???? ??? ???\n\n'
          '??? ????:\n'
          '1. ???? ?? 50 ???? ??????? ?? ????\n'
          '2. ??? ??? ??? ?????? ?????? ?? ???? ??? ?? ??????\n'
          '3. ??? ??? ?? ???? ???? ?? ???? ?????? ????\n'
          '4. PDMA KP: 051-9222373\n\n'
          '????: NDMA GLOF ??? ????????';
      if (isRu) return 'GLOF (Glacial Lake Outburst) — Chitral:\n\n'
          '• Chitral mein 53 khatarnak glacial jheelein hain\n'
          '• Yarkhun, Mastuj, Torkhow darya zyada khatra mein hain\n\n'
          'Kya karein:\n'
          '1. Darya se 50 meter unchaai par rahein\n'
          '2. Glacial daryaon ke qareeb raat na guzarein\n'
          '3. Tez guurj sunein to foran inkhla karein\n'
          '4. PDMA KP: 051-9222373\n\n'
          'Source: NDMA GLOF Risk Assessment';
      return 'GLOF (Glacial Lake Outburst Flood) — Chitral:\n\n'
          '• Chitral has 53 potentially dangerous glacial lakes\n'
          '• Yarkhun, Mastuj, Torkhow rivers are high GLOF-risk corridors\n\n'
          'What to do:\n'
          '1. Stay at least 50m above river level during monsoon\n'
          '2. Never camp near glacial rivers overnight (July–September)\n'
          '3. Move immediately if you hear loud rumbling from upstream\n'
          '4. PDMA KP: 051-9222373\n\n'
          'Source: NDMA GLOF Risk Assessment / PDMA KP Guidelines';
    }

    // -- FLOOD ----------------------------------------------------------------
    if (qn.contains('flood') || qn.contains('flash flood')) {
      // After flood
      if (qn.contains('after') || qn.contains('recover') || qn.contains('return')) {
        if (isUr) return '????? ?? ??? ??? ????:\n\n'
            '1. ?? ?? PDMA KP ????? ???? ?? ??? ??? ???? ?? ?????\n'
            '2. ?????? ???? ?? ??? ???? — ????? ?? ???? ??\n'
            '3. ???? ?? ???? ???? ??????\n'
            '4. ????? ?? ??????? ??? — ????? ?? ??? ????? ??\n'
            '5. PDMA KP ?? DDMA ?? ????? ?? ??? ????? ????\n\n'
            '????: NDMA ??? ?????? ????? 2023-24';
        return 'What to do AFTER a Flood:\n\n'
            '1. Do NOT return home until authorities declare it safe\n'
            '2. Avoid all floodwater — it is contaminated\n'
            '3. Boil ALL drinking water for 2 weeks\n'
            '4. Document damage with photos for relief claims\n'
            '5. Register with PDMA KP/DDMA for flood relief\n'
            '6. Watch for waterborne diseases — typhoid, cholera\n\n'
            'Emergency: PDMA KP 051-9222373 | NDMA 051-9246136\n\n'
            'Source: NDMA Flood Situation Report 2023-24';
      }
      // Before flood / preparedness
      if (qn.contains('before') || qn.contains('prepare') || qn.contains('prevent')) {
        if (isUr) return '????? ?? ???? ?????:\n\n'
            '1. ????? — ??? ?? ???? ?? ?????? ?? ???? ????\n'
            '2. ?? ??? ???? ????: 3 ?? ?? ????? ?????? ??????? CNIC\n'
            '3. ???? ???? ????? ??? ??? ?????? ????? ??? ????\n'
            '4. ???? ????? ????: ?????? 1122? PDMA 051-9222373\n'
            '5. ??? ??? ??? ?????? PMD ????? ??? ???? ??? ????\n\n'
            '????: NDMA ????? ??? ??????? ?????? 2024';
        return 'How to Prepare BEFORE a Flood:\n\n'
            '1. Know your risk — are you near Chitral River or steep slopes?\n'
            '2. Prepare Go-Bag: 3-day water, food, medicines, CNIC copies\n'
            '3. Identify nearest evacuation route and high ground shelter\n'
            '4. Save emergency numbers: Rescue 1122, PDMA KP 051-9222373\n'
            '5. Check PMD weather forecast daily during July–September\n'
            '6. Keep phone charged and power bank ready\n\n'
            'Source: NDMA Preparedness and Preventive Measures 2024';
      }
      // Flood risk
      if (qn.contains('risk') || qn.contains('danger') || qn.contains('cause') ||
          qn.contains('why') || qn.contains('chitral')) {
        if (isUr) return '????? ??? ????? ?? ????:\n\n'
            '• ????? ????? ??? ?? ??? ?? ????? ????? ?? ???? ??\n'
            '• GLOF — ?????? ???? ?? ????? — ????? ????? ??? ??? ???? ??\n'
            '• 2022 ??????? ?????: 1730 ?????? 33 ???? ???????\n'
            '• ??? ??? ??????–????? — ?? ?? ????? ???? ?? ???\n\n'
            '????: NDMA ??? ?????? ????? 2023-24';
        return 'Flood Risk in Chitral / KP:\n\n'
            '• Chitral is highly prone to flash floods due to steep terrain\n'
            '• GLOF (Glacial Lake Outburst) is a critical threat in upper Chitral\n'
            '• 2022 Pakistan floods: 1,730 deaths, 33 million affected — KP severely impacted\n'
            '• Flash flooding occurs with little warning — river rises within minutes\n'
            '• Monsoon season July–September is peak risk period\n\n'
            'Source: NDMA Flood Situation Report 2023-24 / NDMA DRM Strategy 2024';
      }
      // Default — during flood
      if (isUr) return '????? ?? ????? ??? ????:\n\n'
          '1. ???? ??? ?? ????? ??? ?? ??? ????? — ?????? ?? ????\n'
          '2. ?????? ???? ??? ???? ?? ???? ?? ???? ?? ?????\n'
          '3. ??? ???? ???? ???? ?? ???? ?? ??? ?? ????\n'
          '4. ???? ?? ????? ???? ??? ????\n'
          '5. ?????? 1122 ?? ??? ???? ??? ??? ?? ???? ??\n'
          '6. PDMA KP ??? ????? ???????? ?? ?????? ?? ??? ????\n\n'
          '?????? ?????:\n• ?????? 1122\n• PDMA KP: 051-9222373\n• NDMA: 051-9246136\n\n'
          '????: NDMA ??????? / PDMA KP ?????? ????? ???????';
      if (isRu) return 'Seelab ke doran kya karein:\n\n'
          '1. Foran unchi jagah ki taraf jayein — intezaar na karein\n'
          '2. Seelabi paani mein paidal ya gaari se hargiz na jayein\n'
          '3. Tez bahao wale paani ke pulon ko paar na karein\n'
          '4. Bijli ka main switch band karein\n'
          '5. Rescue 1122 call karein agar jaan ko khatra ho\n\n'
          'Emergency:\n• Rescue 1122\n• PDMA KP: 051-9222373\n\n'
          'Source: NDMA / PDMA KP Official Flood Guidelines';
      return 'What to do During a FLOOD:\n\n'
          '1. Move to higher ground IMMEDIATELY — do NOT wait\n'
          '2. Never walk, swim, or drive through floodwater\n'
          '3. Avoid all bridges over fast-moving water\n'
          '4. Turn off electricity at the main switch\n'
          '5. Call Rescue 1122 immediately if lives are in danger\n'
          '6. Follow all PDMA KP and local authority instructions\n\n'
          'Emergency Contacts:\n'
          '• Rescue 1122 (KP — 24/7)\n'
          '• PDMA KP: 051-9222373\n'
          '• NDMA: 051-9246136\n\n'
          'Source: NDMA Pakistan / PDMA KP Official Flood Guidelines';
    }

    // -- EARTHQUAKE -----------------------------------------------------------
    if (qn.contains('earthquake') || qn.contains('seismic') || qn.contains('quake')) {
      if (qn.contains('after') || qn.contains('recover')) {
        if (isUr) return '????? ?? ??? ??? ????:\n\n'
            '1. ???? ???? ?? ?????? ???? — ?????? ????\n'
            '2. ??? ??? ??? ???? — ?? ??? ?? ???? ??? ??????\n'
            '3. ???? ??? ?????? ??? ???? ?? ???\n'
            '4. ?????? 1122 — ?????? ??? ?? ???\n\n'
            '????: NDMA ????? ??????? ?????? ???? 2024';
        return 'What to do AFTER an Earthquake:\n\n'
            '1. Expect aftershocks — stay alert\n'
            '2. Check for gas leaks — smell gas? Leave immediately\n'
            '3. Do not re-enter damaged buildings until declared safe\n'
            '4. Check for injuries — do not move seriously injured\n'
            '5. Listen to NDMA/PDMA emergency broadcasts\n'
            '6. Call Rescue 1122 for emergency assistance\n\n'
            'Source: NDMA National Disaster Response Plan 2024-25';
      }
      if (qn.contains('risk') || qn.contains('chitral') || qn.contains('cause')) {
        return 'Earthquake Risk in Chitral / KP:\n\n'
            '• Chitral is in a seismically active zone — Hindu Kush region\n'
            '• Northern Pakistan sits near the Indian-Eurasian tectonic collision zone\n'
            '• 2005 Kashmir earthquake (7.6 magnitude): 73,000+ deaths in northern Pakistan\n'
            '• Hindu Kush experiences multiple magnitude 5+ earthquakes every year\n'
            '• Old stone/mud-brick construction in Chitral is highly vulnerable\n\n'
            'Source: NDMA DRM Strategy 2024 / NDMA National Disaster Response Plan 2024';
      }
      if (qn.contains('before') || qn.contains('prepare')) {
        return 'How to Prepare BEFORE an Earthquake:\n\n'
            '1. Identify safe spots in each room — under sturdy tables, away from windows\n'
            '2. Secure heavy furniture and shelves to walls\n'
            '3. Know how to turn off gas, water, electricity at main switches\n'
            '4. Practice DROP, COVER, HOLD ON with family members\n'
            '5. Keep emergency kit: water, food, first aid, torch, whistle\n\n'
            'Source: NDMA National Disaster Response Plan 2024-25';
      }
      // Default — during earthquake
      if (isUr) return '????? ?? ????? ??? ????:\n\n'
          '1. ???? ??? ?? ?????? ?? ???? ????? (DROP)\n'
          '2. ????? ??? ?? ???? ??? ????? (COVER)\n'
          '3. ?? ??? ???? ?? ?????? ?? ??????? (HOLD ON)\n'
          '4. ????? ???? ???? ?? ???? ????\n'
          '5. ??? ??????? ?? ????\n'
          '6. ?????? 1122 — ?????? ??? ?? ???\n\n'
          '????: NDMA ????? ??????? ?????? ???? 2024';
      if (isRu) return 'Zalzale ke doran kya karein:\n\n'
          '1. Foran ghutnon par baith jayein (DROP)\n'
          '2. Mazboot mez ke neeche chup jayein (COVER)\n'
          '3. Sar aur gardan ko baazuon se dhanpein (HOLD ON)\n'
          '4. Zalzala mukammal rukne tak andar rahein\n'
          '5. Rescue 1122 — Emergency madad ke liye\n\n'
          'Source: NDMA National Disaster Response Plan 2024';
      return 'What to do During an EARTHQUAKE:\n\n'
          '1. DROP to hands and knees immediately\n'
          '2. Take COVER under a sturdy table, away from windows\n'
          '3. HOLD ON — protect your head and neck\n'
          '4. STAY INSIDE until shaking completely stops\n'
          '5. NEVER use elevators during or after an earthquake\n\n'
          'After shaking stops:\n'
          '• Call Rescue 1122 if anyone is injured\n'
          '• Check for gas leaks before using any switches\n\n'
          'Source: NDMA National Disaster Response Plan 2024-25';
    }

    // -- LANDSLIDE ------------------------------------------------------------
    if (qn.contains('landslide') || qn.contains('mudslide') || qn.contains('debris')) {
      if (qn.contains('sign') || qn.contains('warn') || qn.contains('detect')) {
        return 'Warning Signs of a Landslide:\n\n'
            '1. New cracks or bulges appearing in the ground or slopes\n'
            '2. Tilting trees, fences, or utility poles on hillsides\n'
            '3. Unusual sounds — cracking trees, boulders knocking\n'
            '4. Stream water suddenly becomes muddy or turbid\n'
            '5. Doors and windows sticking (ground movement)\n'
            '6. Small stones rolling down slopes unexpectedly\n\n'
            'If you see these signs — evacuate IMMEDIATELY.\n\n'
            'Source: PDMA KP Flash Floods & GLOF — Chitral Guidelines';
      }
      if (qn.contains('risk') || qn.contains('cause') || qn.contains('chitral')) {
        return 'Landslide Risk in Chitral / KP:\n\n'
            '• Chitral\'s steep valleys make it extremely vulnerable to landslides\n'
            '• Heavy rainfall >50mm in 24 hours is the primary trigger\n'
            '• Deforestation and road construction have increased landslide risk\n'
            '• Earthquake-triggered landslides are a major secondary hazard\n'
            '• Monsoon July–September is peak landslide season\n\n'
            'Source: PDMA KP Flood & Landslide Contingency Plan 2026';
      }
      if (qn.contains('after')) {
        return 'What to do AFTER a Landslide:\n\n'
            '1. Stay away — additional slides frequently follow\n'
            '2. Check for injured — do NOT move seriously injured people\n'
            '3. Report to PDMA KP: 051-9222373\n'
            '4. Watch for flooding which often follows a landslide\n'
            '5. Do not re-enter area until PDMA/DDMA declares it safe\n\n'
            'Source: PDMA KP Flash Floods & GLOF Guidelines';
      }
      // Default — during landslide
      if (isUr) return '???? ?????? ?? ????? ??? ????:\n\n'
          '1. ???? ??? ?? ???? ?????? ?? ????? ?? ????? ??? ??? ??????\n'
          '2. ?????? ??? ????? ?????? ?? ??? ????\n'
          '3. ??? ?????? ?????? ???? — ?????? ?? ?????? ?????? ?? ????\n'
          '4. PDMA KP ?? ????? ???: 051-9222373\n\n'
          '????: PDMA KP ???? ??? ??? GLOF ???????';
      return 'What to do During a LANDSLIDE:\n\n'
          '1. Move away from the path — run PERPENDICULAR to the slide direction\n'
          '2. If escape impossible — curl tight and protect your head\n'
          '3. Avoid river valleys and low-lying areas during rainfall\n'
          '4. Listen for unusual sounds — cracking, rumbling, boulders\n'
          '5. If near a stream — watch for sudden water colour change\n\n'
          'Emergency:\n'
          '• Rescue 1122 (KP — 24/7)\n'
          '• PDMA KP: 051-9222373\n\n'
          'Source: PDMA KP Flash Floods & GLOF — Chitral Guidelines';
    }

    // -- HEAVY RAIN / MONSOON -------------------------------------------------
    if (qn.contains('rain') || qn.contains('monsoon') || qn.contains('storm')) {
      if (qn.contains('risk') || qn.contains('chitral') || qn.contains('forecast')) {
        return 'Heavy Rain Risk — Chitral / KP:\n\n'
            '• Chitral annual rainfall 400–500mm, concentrated in July–September\n'
            '• Cloud bursts increasingly common due to climate change\n'
            '• Heavy rain can trigger flash floods within MINUTES in Chitral\n'
            '• PMD issues 72-hour advance heavy rain warnings\n\n'
            'Monitor: pmd.gov.pk daily during monsoon season\n\n'
            'Source: NDMA Monsoon Preparedness Advisory 2025';
      }
      if (isUr) return '???? ???? ?? ?????:\n\n'
          '1. ??? ????? ??? ???? ????? ?? ????? ?????\n'
          '2. ?????? ????? ???? ?? ????\n'
          '3. ??? ??? ?? ????? ??? ?? ???? ??? ??????? ?? ??? ????\n'
          '4. PDMA KP ??? PMD ?? ??????? ??? ????\n'
          '5. ?????? ?? ???? ?????\n\n'
          '?????? ?????:\n• ?????? 1122\n• PDMA KP: 051-9222373\n\n'
          '????: NDMA ??? ??? ????? ?????? 2025';
      if (isRu) return 'Bhari barish ke doran:\n\n'
          '1. Nadi nalon aur darya kinare se faasla rakhein\n'
          '2. Seelabi sadkein uboor na karein\n'
          '3. PDMA KP aur PMD ki ittilayein check karein\n'
          '4. Emergency kit tayyar rakhein\n\n'
          'Emergency:\n• Rescue 1122\n• PDMA KP: 051-9222373\n\n'
          'Source: NDMA Monsoon Preparedness Advisory 2025';
      return 'What to do During HEAVY RAIN:\n\n'
          '1. Stay away from all rivers, nullahs, and low-lying areas\n'
          '2. Do NOT cross flooded roads or streams — turn around\n'
          '3. Stay indoors away from windows during thunderstorms\n'
          '4. Keep drains and gutters clear to prevent waterlogging\n'
          '5. Monitor PDMA KP and PMD alerts on your phone\n'
          '6. Have emergency kit ready: torch, water, first aid, documents\n\n'
          'Emergency:\n• Rescue 1122 | PDMA KP: 051-9222373 | PMD: 051-9250363\n\n'
          'Source: NDMA Monsoon Preparedness Advisory 2025';
    }

    // -- EMERGENCY CONTACTS ---------------------------------------------------
    if (qn.contains('emergency') || qn.contains('contact') || qn.contains('number') ||
        qn.contains('1122') || qn.contains('help') || qn.contains('call')) {
      if (isUr) return '?????? ????? — ????? / KP:\n\n'
          '1. ?????? 1122 — KP ?????? ?????? (24/7? ???)\n'
          '2. PDMA KP ???? ???? — 051-9222373\n'
          '3. NDMA ???? ???? — 051-9246136\n'
          '4. ????? ??????? — 051-9250363\n'
          '5. ????? ???????? — 115\n'
          '6. ??? ??? ????? ????? ????? — 0943-412093\n'
          '7. ???? ???????? ????? — 0943-412022\n\n'
          '????: NDMA / PDMA KP ?????? ?????';
      if (isRu) return 'Emergency Contacts — Chitral / KP:\n\n'
          '1. Rescue 1122 — KP Emergency (24/7, Free)\n'
          '2. PDMA KP — 051-9222373\n'
          '3. NDMA — 051-9246136\n'
          '4. PMD Weather — 051-9250363\n'
          '5. Edhi Foundation — 115\n'
          '6. AKHS Chitral — 0943-412093\n\n'
          'Source: NDMA / PDMA KP Official Channels';
      return 'Emergency Contacts — Chitral / KP, Pakistan:\n\n'
          '1. Rescue 1122 — KP Emergency Rescue (24/7, FREE)\n'
          '2. PDMA KP Helpline — 051-9222373\n'
          '3. NDMA Helpline — 051-9246136\n'
          '4. Pakistan Met Dept — 051-9250363\n'
          '5. Edhi Foundation — 115\n'
          '6. Aga Khan Health Services Chitral — 0943-412093\n'
          '7. District Administration Chitral — 0943-412022\n\n'
          'Source: NDMA / PDMA KP Official Emergency Channels';
    }

    // -- GO-BAG / EMERGENCY KIT -----------------------------------------------
    if (qn.contains('kit') || qn.contains('bag') || qn.contains('pack') ||
        qn.contains('checklist') || qn.contains('72 hours')) {
      if (isUr) return '?????? ??? ??? ??? (NDMA ???????):\n\n'
          '1. ???? — 3 ?? ?? ?????? (3 ???? ?? ???)\n'
          '2. ????? — 3 ?? ?? ??? (????? ??? ????)\n'
          '3. ???? ??? ?? — ?????? ????\n'
          '4. ????????? — CNIC ?????? ???? ???? ??? ???\n'
          '5. ???? ??? ???? ????\n'
          '6. ???? — ???? ??? ?????? ?? ??? ?? ???\n'
          '7. ??? ???? — ????? ??? ??? ?? ???? ???? ??\n'
          '8. ??? ??? — ????? ????? ???\n\n'
          '????: NDMA ????? ?? ??????? 2024';
      return 'Go-Bag / Emergency Kit Checklist (NDMA Guidelines):\n\n'
          '1. Water — 3-day supply (3 litres per person per day)\n'
          '2. Food — Non-perishable for 3 days (biscuits, dry fruit)\n'
          '3. First Aid Kit — bandages, antiseptic, medications\n'
          '4. Documents — CNIC copies in waterproof bag\n'
          '5. Torch and power bank (fully charged)\n'
          '6. Whistle — to signal rescuers if trapped\n'
          '7. Warm clothing — temperatures drop sharply in Chitral at night\n'
          '8. Cash in small denominations (ATMs fail in disasters)\n\n'
          'Keep your Go-Bag accessible at all times during monsoon.\n\n'
          'Source: NDMA Pakistan Preparedness Guidelines 2024';
    }

    // -- PREPAREDNESS / GENERAL -----------------------------------------------
    if (qn.contains('prepare') || qn.contains('ready') || qn.contains('plan') ||
        qn.contains('before disaster') || qn.contains('what can i do')) {
      if (isUr) return '??? ?? ???? ????? ????? — ?????:\n\n'
          '1. ???? ???? ?????: ?????? ?????? ???? ??????? GLOF\n'
          '2. ??????? ?????? ?????? ??????\n'
          '3. ?? ??? ???? ??? ???? ????? ?????\n'
          '4. ???? ????? ?? ??? ??? ???? ????? ????: 1122? PDMA 051-9222373\n'
          '5. ??? ??? ??? PDMA KP ??? PMD ?? ??????? ??????? ??? ????\n'
          '6. ???? ??? ????? ????? ?? ????? DDMA ??? ????? ????\n\n'
          '????: NDMA ????? ??? ??????? ?????? 2024';
      return 'General Disaster Preparedness — Chitral / KP:\n\n'
          '1. Know your risk — floods, GLOFs, earthquakes, landslides\n'
          '2. Make a family emergency plan and evacuation route\n'
          '3. Prepare a Go-Bag and keep it accessible\n'
          '4. Save emergency numbers in ALL family phones: 1122, PDMA 051-9222373\n'
          '5. Monitor PDMA KP and PMD during monsoon season (July–September)\n'
          '6. Register elderly/disabled family with local DDMA Chitral\n'
          '7. Identify your nearest evacuation shelter location\n\n'
          'Source: NDMA Preparedness and Preventive Measures 2024';
    }

    // -- NDMA / PDMA INFO -----------------------------------------------------
    if (qn.contains('ndma') || qn.contains('pdma') || qn.contains('guidelines') ||
        qn.contains('authority') || qn.contains('government')) {
      return 'NDMA & PDMA KP — Official Disaster Management:\n\n'
          'NDMA (National Disaster Management Authority):\n'
          '• Pakistan\'s apex body for disaster risk management\n'
          '• Issues monsoon advisories, situation reports, DRM strategy\n'
          '• Website: ndma.gov.pk | Helpline: 051-9246136\n\n'
          'PDMA KP (Provincial Disaster Management Authority):\n'
          '• KP-level disaster coordination for Chitral and all KP districts\n'
          '• Issues Chitral-specific flood, GLOF, and landslide warnings\n'
          '• Helpline: 051-9222373 | Website: pdma.gov.pk\n\n'
          'This app uses 13 official PDFs from NDMA and PDMA KP\n'
          '— 315 verified text chunks for knowledge retrieval.\n\n'
          'Source: NDMA / PDMA KP Official Channels';
    }

    // -- GENERAL FALLBACK -----------------------------------------------------
    if (isUr) return 'ChitralSafe — ????? ?? ??? ??? ?? ?????:\n\n'
        '1. ???? ???? ?????: ?????? ?????? ???? ??????? GLOF\n'
        '2. ?????? ??? ???? ?????: ????? ?????? ??????? ?????????\n'
        '3. ???? ????? ????: ?????? 1122? PDMA 051-9222373\n'
        '4. NDMA ??? PDMA KP ?? ??????? ??? ????\n\n'
        '??? ?? ??????:\n'
        '• ????? ?? ????? ??? ????\n'
        '• ????? ?? ?????\n'
        '• ???? ?????? ??????\n'
        '• ?????? ?????\n'
        '• ?? ??? ??? ???\n\n'
        '????: NDMA / PDMA KP ?????? ???????';
    if (isRu) return 'ChitralSafe — Chitral ke liye aafat se hifazat:\n\n'
        '1. Apna khatra janein: seelab, zalzala, landslide, GLOF\n'
        '2. Emergency bag tayyar rakhein\n'
        '3. Numbers save karein: 1122, PDMA 051-9222373\n'
        '4. NDMA aur PDMA KP ki ittilayein check karein\n\n'
        'Mujhse poochhein:\n'
        '• Seelab ke doran kya karein\n'
        '• Zalzala se hifazat\n'
        '• Landslide ihtiyaat\n'
        '• Emergency contacts\n'
        '• Go-Bag checklist\n\n'
        'Source: NDMA / PDMA KP Official Guidelines';
    return 'ChitralSafe — Disaster Safety for Chitral, KP:\n\n'
        'I can answer questions about:\n'
        '• Floods (during / before / after / risk)\n'
        '• Earthquakes (DROP-COVER-HOLD ON)\n'
        '• Landslides (warning signs, what to do)\n'
        '• GLOF — Glacial Lake Outburst Floods\n'
        '• Heavy rain and monsoon safety\n'
        '• Emergency contacts (Rescue 1122, PDMA KP)\n'
        '• Go-Bag / emergency kit checklist\n'
        '• General disaster preparedness\n\n'
        'Try asking: "What should I do during a flood?"\n\n'
        'Source: NDMA / PDMA KP Official Guidelines';
  }
  Widget _buildFormattedText(String text) {
    final lines = text.split('\n');
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: lines.map((line) {
        // Empty line = small spacer
        if (line.trim().isEmpty) return const SizedBox(height: 6);

        // Bold header line: **Some Title**
        if (line.trim().startsWith('**') && line.trim().endsWith('**')) {
          final content = line.trim().replaceAll('**', '');
          return _headerWidget(content);
        }

        // Header ending with colon (e.g. "What to do During a FLOOD:")
        if (line.trim().endsWith(':') && !line.trim().startsWith('•') && !line.trim().startsWith('-')) {
          final isFirstLine = lines.indexOf(line) == 0;
          return Padding(
            padding: EdgeInsets.only(bottom: 8, top: isFirstLine ? 0 : 8),
            child: Text(
              line.trim(),
              style: AppTextStyles.body.copyWith(
                color: AppColors.primary,
                fontWeight: FontWeight.w700,
                fontSize: 15,
                height: 1.4,
              ),
            ),
          );
        }

        // Numbered list: 1. text
        final numberedMatch = RegExp(r'^(\d+)\.\s+(.+)$').firstMatch(line.trim());
        if (numberedMatch != null) {
          final num = numberedMatch.group(1)!;
          final content = numberedMatch.group(2)!;
          return Padding(
            padding: const EdgeInsets.only(bottom: 5, left: 4),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  width: 22,
                  height: 22,
                  margin: const EdgeInsets.only(right: 8, top: 1),
                  decoration: const BoxDecoration(
                    color: AppColors.primary,
                    shape: BoxShape.circle,
                  ),
                  child: Center(
                    child: Text(
                      num,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                ),
                Expanded(
                  child: Text(
                    content,
                    style: AppTextStyles.body.copyWith(
                      color: AppColors.textPrimary,
                      height: 1.4,
                      fontSize: 14,
                    ),
                  ),
                ),
              ],
            ),
          );
        }

        // Bullet point: • text
        if (line.trim().startsWith('•') || line.trim().startsWith('-')) {
          final content = line.trim().replaceFirst(RegExp(r'^[•\-]\s*'), '');
          return Padding(
            padding: const EdgeInsets.only(bottom: 5, left: 4),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  width: 6,
                  height: 6,
                  margin: const EdgeInsets.only(right: 8, top: 7),
                  decoration: const BoxDecoration(
                    color: AppColors.primary,
                    shape: BoxShape.circle,
                  ),
                ),
                Expanded(
                  child: Text(
                    content,
                    style: AppTextStyles.body.copyWith(
                      color: AppColors.textPrimary,
                      height: 1.4,
                      fontSize: 14,
                    ),
                  ),
                ),
              ],
            ),
          );
        }

        // Italic source line: *Source: ...*
        if (line.trim().startsWith('*') && line.trim().endsWith('*')) {
          final content = line.trim().replaceAll('*', '');
          return Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Text(
              content,
              style: AppTextStyles.caption.copyWith(
                color: AppColors.textMuted,
                fontStyle: FontStyle.italic,
                fontSize: 12,
              ),
            ),
          );
        }

        // Inline bold: text with **bold** parts
        if (line.contains('**')) {
          return Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: _buildInlineBold(line),
          );
        }

        // Normal text
        return Padding(
          padding: const EdgeInsets.only(bottom: 4),
          child: Text(
            line,
            style: AppTextStyles.body.copyWith(
              color: AppColors.textPrimary,
              height: 1.5,
              fontSize: 14,
            ),
          ),
        );
      }).toList(),
    );
  }

  Widget _headerWidget(String content) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6, top: 4),
      child: Text(
        content,
        style: AppTextStyles.body.copyWith(
          color: AppColors.textPrimary,
          fontWeight: FontWeight.w700,
          fontSize: 14,
          height: 1.4,
        ),
      ),
    );
  }

  /// Renders a line with **bold** segments inline
  Widget _buildInlineBold(String line) {
    final parts = line.split('**');
    final spans = <TextSpan>[];
    for (int i = 0; i < parts.length; i++) {
      if (parts[i].isEmpty) continue;
      spans.add(TextSpan(
        text: parts[i],
        style: TextStyle(
          fontWeight: i.isOdd ? FontWeight.w700 : FontWeight.normal,
          color: AppColors.textPrimary,
          fontSize: 14,
          height: 1.5,
        ),
      ));
    }
    return RichText(text: TextSpan(children: spans));
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent + 200,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  String _evidenceLabel(EvidenceLevel level) {
    switch (level) {
      case EvidenceLevel.high:
        return Tr.t('evidence_high');
      case EvidenceLevel.moderate:
        return Tr.t('evidence_moderate');
      case EvidenceLevel.limited:
        return Tr.t('evidence_limited');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: _buildAppBar(),
      body: Column(
        children: [
          _buildContextChips(),
          Expanded(child: _buildChatArea()),
          _buildDisclaimer(),
          _buildInputBar(),
        ],
      ),
    );
  }

  PreferredSizeWidget _buildAppBar() {
    return AppBar(
      backgroundColor: AppColors.surface,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      leading: const BackButton(color: AppColors.textPrimary),
      title: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            Tr.t('chat_title'),
            style: AppTextStyles.cardTitle.copyWith(
              color: AppColors.textPrimary,
              fontSize: 17,
            ),
          ),
          Text(
            Tr.t('chat_subtitle'),
            style: AppTextStyles.caption.copyWith(
              color: AppColors.textSecondary,
              fontSize: 11,
            ),
          ),
        ],
      ),
      actions: [
        Container(
          margin: const EdgeInsets.only(right: 16),
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
          decoration: BoxDecoration(
            color: _isOnline
                ? AppColors.onlineGreen.withValues(alpha: 0.12)
                : AppColors.border,
            borderRadius: BorderRadius.circular(20),
            border: Border.all(
              color: _isOnline
                ? AppColors.onlineGreen.withValues(alpha: 0.4)
                : AppColors.textMuted.withValues(alpha: 0.3),
            ),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 7,
                height: 7,
                decoration: BoxDecoration(
                  color: _isOnline ? AppColors.onlineGreen : AppColors.textMuted,
                  shape: BoxShape.circle,
                ),
              ),
              const SizedBox(width: 5),
              Text(
                _isOnline ? Tr.t('chat_online') : Tr.t('chat_offline'),
                style: AppTextStyles.caption.copyWith(
                  fontWeight: FontWeight.w600,
                  color: _isOnline ? AppColors.onlineGreen : AppColors.textMuted,
                  fontSize: 12,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildContextChips() {
    return Container(
      color: AppColors.surface,
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Row(
          children: [
            _contextChip(
              icon: Icons.location_on_outlined,
              label: Tr.t('chat_context_location'),
              color: AppColors.textSecondary,
            ),
            const SizedBox(width: 8),
            _contextChip(
              icon: Icons.warning_amber_rounded,
              label: Tr.t('chat_context_alert'),
              color: AppColors.riskHigh,
              bgColor: AppColors.riskHighBg,
              borderColor: AppColors.riskHighCardBorder,
            ),
          ],
        ),
      ),
    );
  }

  Widget _contextChip({
    required IconData icon,
    required String label,
    required Color color,
    Color? bgColor,
    Color? borderColor,
  }) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: bgColor ?? AppColors.surfaceVariant,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: borderColor ?? AppColors.border),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 13, color: color),
          const SizedBox(width: 4),
          Text(
            label,
            style: AppTextStyles.caption.copyWith(
              color: color,
              fontSize: 12,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildChatArea() {
    final bool isEmpty = _messages.isEmpty;
    final itemCount = (isEmpty ? 2 : _messages.length + 1) + (_loading ? 1 : 0);

    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
      itemCount: itemCount,
      itemBuilder: (context, index) {
        if (index == 0) return _buildGreetingBubble();
        if (isEmpty && index == 1) return _buildSuggestionChips();
        final msgIndex = isEmpty ? index - 2 : index - 1;
        if (msgIndex >= 0 && msgIndex < _messages.length) {
          return _buildMessageBubble(_messages[msgIndex], msgIndex);
        }
        if (_loading) return _buildLoadingBubble();
        return const SizedBox.shrink();
      },
    );
  }

  Widget _buildGreetingBubble() {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _aiAvatar(),
          const SizedBox(width: 10),
          Expanded(
            child: Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: const BorderRadius.only(
                  topLeft: Radius.circular(4),
                  topRight: Radius.circular(16),
                  bottomLeft: Radius.circular(16),
                  bottomRight: Radius.circular(16),
                ),
                border: Border.all(color: AppColors.border),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.04),
                    blurRadius: 8,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: Text(
                Tr.t('chat_greeting'),
                style: AppTextStyles.body.copyWith(
                  color: AppColors.textPrimary,
                  height: 1.5,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSuggestionChips() {
    return Padding(
      padding: const EdgeInsets.only(bottom: 20),
      child: Column(
        children: _suggestionChips
            .map(
              (chip) => Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: GestureDetector(
                  onTap: () => _submitQuery(chip),
                  child: Container(
                    width: double.infinity,
                    padding: const EdgeInsets.symmetric(
                        horizontal: 16, vertical: 11),
                    decoration: BoxDecoration(
                      color: AppColors.surface,
                      borderRadius: BorderRadius.circular(24),
                      border: Border.all(color: AppColors.border),
                    ),
                    child: Text(
                      chip,
                      style: AppTextStyles.body.copyWith(
                        color: AppColors.textSecondary,
                        fontSize: 14,
                      ),
                    ),
                  ),
                ),
              ),
            )
            .toList(),
      ),
    );
  }

  Widget _buildMessageBubble(_ChatMessage msg, int index) {
    if (msg.isUser) {
      return Padding(
        padding: const EdgeInsets.only(bottom: 16, left: 48),
        child: Align(
          alignment: Alignment.centerRight,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
            decoration: const BoxDecoration(
              color: AppColors.primary,
              borderRadius: BorderRadius.only(
                topLeft: Radius.circular(16),
                topRight: Radius.circular(4),
                bottomLeft: Radius.circular(16),
                bottomRight: Radius.circular(16),
              ),
            ),
            child: Text(
              msg.text,
              style: AppTextStyles.body.copyWith(
                color: Colors.white,
                height: 1.5,
              ),
            ),
          ),
        ),
      );
    }

    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _aiAvatar(),
          const SizedBox(width: 10),
          Expanded(
            child: Container(
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: const BorderRadius.only(
                  topLeft: Radius.circular(4),
                  topRight: Radius.circular(16),
                  bottomLeft: Radius.circular(16),
                  bottomRight: Radius.circular(16),
                ),
                border: Border.all(color: AppColors.border),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.04),
                    blurRadius: 8,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Padding(
                    padding: const EdgeInsets.fromLTRB(16, 16, 16, 12),
                    child: _buildFormattedText(msg.text),
                  ),
                  if (msg.recommendedSteps.isNotEmpty)
                    Padding(
                      padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
                      child: Container(
                        padding: const EdgeInsets.all(14),
                        decoration: BoxDecoration(
                          color: AppColors.aiCardBg,
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: AppColors.aiCardBorder),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              Tr.t('chat_recommended_steps'),
                              style: AppTextStyles.caption.copyWith(
                                fontWeight: FontWeight.w700,
                                color: AppColors.textPrimary,
                              ),
                            ),
                            const SizedBox(height: 8),
                            ...msg.recommendedSteps.map(
                              (step) => Padding(
                                padding: const EdgeInsets.only(bottom: 6),
                                child: Row(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    const Icon(
                                      Icons.check_circle_outline,
                                      size: 16,
                                      color: AppColors.primary,
                                    ),
                                    const SizedBox(width: 8),
                                    Expanded(
                                      child: Text(
                                        step,
                                        style: AppTextStyles.caption.copyWith(
                                          color: AppColors.textPrimary,
                                          height: 1.4,
                                        ),
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  InkWell(
                    onTap: () {
                      setState(() {
                        _messages[index].xaiExpanded =
                            !_messages[index].xaiExpanded;
                      });
                    },
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 16, vertical: 12),
                      decoration: const BoxDecoration(
                        border: Border(
                          top: BorderSide(color: AppColors.border),
                        ),
                      ),
                      child: Row(
                        children: [
                          const Icon(
                            Icons.psychology_outlined,
                            size: 16,
                            color: AppColors.primary,
                          ),
                          const SizedBox(width: 6),
                          Expanded(
                            child: Text(
                              Tr.t('chat_xai_label'),
                              style: AppTextStyles.caption.copyWith(
                                color: AppColors.primary,
                                fontWeight: FontWeight.w600,
                                fontSize: 13,
                              ),
                            ),
                          ),
                          Icon(
                            msg.xaiExpanded
                                ? Icons.keyboard_arrow_up
                                : Icons.keyboard_arrow_down,
                            size: 18,
                            color: AppColors.textMuted,
                          ),
                        ],
                      ),
                    ),
                  ),
                  if (msg.xaiExpanded)
                    Padding(
                      padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const SizedBox(height: 8),
                          if (msg.evidenceLevel != null) ...[
                            Row(children: [
                              Text(
                                Tr.t('xai_evidence_label'),
                                style: AppTextStyles.caption.copyWith(
                                  color: AppColors.textMuted,
                                  fontSize: 12,
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                              Text(
                                msg.evidenceLevel!,
                                style: AppTextStyles.caption.copyWith(
                                  color: AppColors.primary,
                                  fontSize: 12,
                                ),
                              ),
                            ]),
                            const SizedBox(height: 6),
                          ],
                          if (msg.sources.isNotEmpty) ...[
                            Text(
                              Tr.t('xai_sources_label'),
                              style: AppTextStyles.caption.copyWith(
                                color: AppColors.textMuted,
                                fontWeight: FontWeight.w600,
                                fontSize: 12,
                              ),
                            ),
                            const SizedBox(height: 4),
                            ...msg.sources.map(
                              (s) => Padding(
                                padding: const EdgeInsets.only(bottom: 3),
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    // Source name line
                                    Text(
                                      '• ${s.split('\n').first}',
                                      style: AppTextStyles.caption.copyWith(
                                        color: AppColors.textMuted,
                                        fontSize: 12,
                                      ),
                                    ),
                                    // URL line (if present)
                                    if (s.contains('\n'))
                                      Text(
                                        s.split('\n').last,
                                        style: AppTextStyles.caption.copyWith(
                                          color: AppColors.primary,
                                          fontSize: 11,
                                          decoration: TextDecoration.underline,
                                        ),
                                      ),
                                  ],
                                ),
                              ),
                            ),
                          ] else
                            Text(
                              Tr.t('xai_context_note'),
                              style: AppTextStyles.caption.copyWith(
                                color: AppColors.textMuted,
                                fontSize: 12,
                                height: 1.4,
                              ),
                            ),
                        ],
                      ),
                    ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLoadingBubble() {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _aiAvatar(),
          const SizedBox(width: 10),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: AppColors.border),
            ),
            child: const SizedBox(
              width: 24,
              height: 24,
              child: CircularProgressIndicator(
                strokeWidth: 2.5,
                color: AppColors.primary,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _aiAvatar() {
    return Container(
      width: 36,
      height: 36,
      decoration: const BoxDecoration(
        color: AppColors.primary,
        shape: BoxShape.circle,
      ),
      child: const Icon(Icons.smart_toy_outlined, color: Colors.white, size: 18),
    );
  }

  Widget _buildDisclaimer() {
    return Container(
      color: AppColors.surface,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        children: [
          const Icon(Icons.info_outline, size: 13, color: AppColors.textMuted),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              Tr.t('chat_disclaimer'),
              style: AppTextStyles.caption.copyWith(
                color: AppColors.textMuted,
                fontSize: 11,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildInputBar() {
    return Container(
      color: AppColors.surface,
      padding: const EdgeInsets.fromLTRB(16, 8, 12, 16),
      child: SafeArea(
        top: false,
        child: Row(
          children: [
            Expanded(
              child: Container(
                decoration: BoxDecoration(
                  color: AppColors.background,
                  borderRadius: BorderRadius.circular(28),
                  border: Border.all(color: AppColors.border),
                ),
                child: TextField(
                  controller: _controller,
                  style: AppTextStyles.body.copyWith(fontSize: 14),
                  textInputAction: TextInputAction.send,
                  onSubmitted: _loading ? null : _submitQuery,
                  decoration: InputDecoration(
                    hintText: Tr.t('chat_input_hint'),
                    hintStyle: AppTextStyles.body.copyWith(
                      color: AppColors.textDisabled,
                      fontSize: 14,
                    ),
                    border: InputBorder.none,
                    contentPadding: const EdgeInsets.symmetric(
                      horizontal: 18,
                      vertical: 12,
                    ),
                  ),
                ),
              ),
            ),
            const SizedBox(width: 8),
            GestureDetector(
              onTap: _loading ? null : () => _submitQuery(_controller.text),
              child: Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: _loading ? AppColors.textDisabled : AppColors.primary,
                  shape: BoxShape.circle,
                ),
                child: const Icon(
                  Icons.send_rounded,
                  color: Colors.white,
                  size: 20,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}