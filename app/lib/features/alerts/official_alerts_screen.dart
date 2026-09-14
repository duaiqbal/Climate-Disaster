import 'dart:async';

import 'package:flutter/material.dart';
import '../../core/localization/app_translations.dart';
import '../../core/localization/language_service.dart';
import '../../core/models/official_alert.dart';
import '../../core/services/alert_service.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_text_styles.dart';
import 'alert_details_screen.dart';

class OfficialAlertsScreen extends StatefulWidget {
  final Function(OfficialAlert)? onSelectAlert;
  const OfficialAlertsScreen({super.key, this.onSelectAlert});

  @override
  State<OfficialAlertsScreen> createState() => _OfficialAlertsScreenState();
}

class _OfficialAlertsScreenState extends State<OfficialAlertsScreen>
    with WidgetsBindingObserver {
  // ── State ──────────────────────────────────────────────────────────────────
  List<OfficialAlert> _alerts          = [];
  bool                _loading         = true;
  String              _selectedCategory = 'All';

  // In-app notification banner
  OfficialAlert? _newAlertBanner;
  Timer?         _bannerTimer;

  // Real-time stream subscription
  StreamSubscription<OfficialAlert>? _alertSub;

  final List<String> _categories = ['All', 'Flood', 'Landslide', 'Heavy Rain'];

  // ── Lifecycle ───────────────────────────────────────────────────────────────

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);

    // Start AlertService (idempotent — safe to call multiple times)
    AlertService.instance.start();

    // Load initial list from the service's in-memory snapshot
    _syncFromService();

    // Subscribe to live alert stream
    _alertSub = AlertService.instance.alertStream.listen(_onNewAlert);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _alertSub?.cancel();
    _bannerTimer?.cancel();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // Re-subscribe when app comes back to foreground
    if (state == AppLifecycleState.resumed) {
      _syncFromService();
    }
  }

  // ── Data helpers ─────────────────────────────────────────────────────────────

  void _syncFromService() {
    if (!mounted) return;
    setState(() {
      _alerts  = List.of(AlertService.instance.alerts);
      _loading = false;
    });
  }

  Future<void> _refresh() async {
    setState(() => _loading = true);
    await AlertService.instance.refresh();
    _syncFromService();
  }

  // Called by AlertService stream when a new alert arrives via WebSocket / polling
  void _onNewAlert(OfficialAlert alert) {
    if (!mounted) return;
    setState(() {
      // Prepend — newest first
      _alerts = List.of(AlertService.instance.alerts);
    });
    _showBanner(alert);
  }

  // ── In-app notification banner ───────────────────────────────────────────────

  void _showBanner(OfficialAlert alert) {
    _bannerTimer?.cancel();
    setState(() => _newAlertBanner = alert);
    // Auto-dismiss after 5 seconds
    _bannerTimer = Timer(const Duration(seconds: 5), () {
      if (mounted) setState(() => _newAlertBanner = null);
    });
  }

  void _dismissBanner() {
    _bannerTimer?.cancel();
    setState(() => _newAlertBanner = null);
  }

  // ── Filter ───────────────────────────────────────────────────────────────────

  List<OfficialAlert> get _filteredAlerts {
    if (_selectedCategory == 'All') return _alerts;
    return _alerts.where((a) {
      return '${a.title} ${a.description}'
          .toLowerCase()
          .contains(_selectedCategory.toLowerCase());
    }).toList();
  }

  String _categoryLabel(String cat) {
    switch (cat) {
      case 'All':        return Tr.t('cat_all');
      case 'Flood':      return Tr.t('cat_flood');
      case 'Landslide':  return Tr.t('cat_landslide');
      case 'Heavy Rain': return Tr.t('cat_heavy_rain');
      default:           return cat;
    }
  }

  // ── Build ─────────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: _buildAppBar(),
      body: Stack(
        children: [
          Column(
            children: [
              const SizedBox(height: 8),
              _buildConnectionBadge(),
              const SizedBox(height: 8),
              _buildCategoryChips(),
              const SizedBox(height: 12),
              Expanded(child: _buildBody()),
            ],
          ),

          // ── In-app notification banner (slides in from top) ──────────────
          if (_newAlertBanner != null)
            Positioned(
              top: 0, left: 0, right: 0,
              child: _NewAlertBanner(
                alert: _newAlertBanner!,
                onDismiss: _dismissBanner,
                onTap: () {
                  _dismissBanner();
                  Navigator.of(context).push(MaterialPageRoute(
                    builder: (_) =>
                        AlertDetailsScreen(alert: _newAlertBanner!),
                  ));
                },
              ),
            ),
        ],
      ),
    );
  }

  PreferredSizeWidget _buildAppBar() {
    return AppBar(
      backgroundColor: AppColors.surface,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      title: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(Tr.t('alerts_title'), style: AppTextStyles.screenHeader),
          Text(Tr.t('alerts_subtitle'), style: AppTextStyles.caption),
        ],
      ),
      actions: [
        // Manual refresh button
        IconButton(
          icon: const Icon(Icons.refresh, color: AppColors.primary),
          tooltip: 'Refresh alerts',
          onPressed: _refresh,
        ),
      ],
    );
  }

  // Real-time connection status badge
  Widget _buildConnectionBadge() {
    final connected = AlertService.instance.isConnected;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Row(
        children: [
          Container(
            width: 8, height: 8,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: connected ? AppColors.onlineGreen : AppColors.riskModerate,
            ),
          ),
          const SizedBox(width: 6),
          Text(
            connected
                ? (LanguageService.instance.isUrdu
                    ? 'ریئل ٹائم الرٹس فعال'
                    : 'Real-time alerts active')
                : (LanguageService.instance.isUrdu
                    ? 'پولنگ موڈ (ہر 30 سیکنڈ)'
                    : 'Polling mode — updates every 30s'),
            style: AppTextStyles.caption.copyWith(
              color: connected ? AppColors.onlineGreen : AppColors.riskModerate,
              fontWeight: FontWeight.w600,
              fontSize: 12,
            ),
          ),
          const Spacer(),
          Text(
            '${_alerts.length} ${LanguageService.instance.isUrdu ? "الرٹس" : "alerts"}',
            style: AppTextStyles.caption.copyWith(
              color: AppColors.textMuted, fontSize: 12,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCategoryChips() {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Row(
        children: _categories.map((cat) {
          final selected = _selectedCategory == cat;
          return Padding(
            padding: const EdgeInsets.only(right: 8),
            child: ChoiceChip(
              label: Text(_categoryLabel(cat)),
              selected: selected,
              selectedColor: AppColors.primary,
              backgroundColor: AppColors.surface,
              labelStyle: TextStyle(
                color: selected ? Colors.white : AppColors.textSecondary,
                fontWeight: FontWeight.w600,
                fontSize: 13,
              ),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(20),
                side: BorderSide(
                  color: selected ? AppColors.primary : AppColors.border,
                ),
              ),
              onSelected: (_) =>
                  setState(() => _selectedCategory = cat),
            ),
          );
        }).toList(),
      ),
    );
  }

  Widget _buildBody() {
    if (_loading) {
      return const Center(
          child: CircularProgressIndicator(color: AppColors.primary));
    }

    return RefreshIndicator(
      onRefresh: _refresh,
      color: AppColors.primary,
      child: _filteredAlerts.isEmpty
          ? _buildEmpty()
          : ListView.builder(
              padding:
                  const EdgeInsets.symmetric(horizontal: 20, vertical: 4),
              itemCount: _filteredAlerts.length,
              itemBuilder: (_, i) => _AlertCard(
                alert: _filteredAlerts[i],
                onTap: () {
                  if (widget.onSelectAlert != null) {
                    widget.onSelectAlert!(_filteredAlerts[i]);
                  } else {
                    Navigator.of(context).push(MaterialPageRoute(
                      builder: (_) =>
                          AlertDetailsScreen(alert: _filteredAlerts[i]),
                    ));
                  }
                },
              ),
            ),
    );
  }

  Widget _buildEmpty() {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.notifications_none,
              size: 52, color: AppColors.textMuted),
          const SizedBox(height: 14),
          Text(
            Tr.t('no_alerts_filter'),
            style: AppTextStyles.body.copyWith(color: AppColors.textMuted),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 8),
          TextButton.icon(
            onPressed: _refresh,
            icon: const Icon(Icons.refresh, size: 16),
            label: Text(Tr.t('retry')),
          ),
        ],
      ),
    );
  }
}

// ── In-app notification banner ──────────────────────────────────────────────

class _NewAlertBanner extends StatefulWidget {
  final OfficialAlert alert;
  final VoidCallback   onDismiss;
  final VoidCallback   onTap;

  const _NewAlertBanner({
    required this.alert,
    required this.onDismiss,
    required this.onTap,
  });

  @override
  State<_NewAlertBanner> createState() => _NewAlertBannerState();
}

class _NewAlertBannerState extends State<_NewAlertBanner>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;
  late final Animation<Offset>   _slide;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 350));
    _slide = Tween<Offset>(
      begin: const Offset(0, -1),
      end:   Offset.zero,
    ).animate(CurvedAnimation(parent: _ctrl, curve: Curves.easeOutCubic));
    _ctrl.forward();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isHigh = widget.alert.severity.toLowerCase() == 'high';
    final bg     = isHigh ? AppColors.riskHigh : AppColors.riskModerate;

    return SlideTransition(
      position: _slide,
      child: SafeArea(
        bottom: false,
        child: GestureDetector(
          onTap: widget.onTap,
          child: Container(
            margin: const EdgeInsets.fromLTRB(12, 8, 12, 0),
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              color: bg,
              borderRadius: BorderRadius.circular(14),
              boxShadow: [
                BoxShadow(
                  color: bg.withValues(alpha: 0.45),
                  blurRadius: 16,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: Row(
              children: [
                // Pulsing bell icon
                const Icon(Icons.notifications_active,
                    color: Colors.white, size: 22),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 6, vertical: 2),
                            decoration: BoxDecoration(
                              color: Colors.white.withValues(alpha: 0.25),
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: Text(
                              LanguageService.instance.isUrdu
                                  ? 'نئی اطلاع'
                                  : 'NEW ALERT',
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 10,
                                fontWeight: FontWeight.w800,
                                letterSpacing: 0.5,
                              ),
                            ),
                          ),
                          const SizedBox(width: 6),
                          Text(
                            widget.alert.issuedAgo,
                            style: TextStyle(
                              color: Colors.white.withValues(alpha: 0.85),
                              fontSize: 11,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 4),
                      Text(
                        widget.alert.title,
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 13,
                          fontWeight: FontWeight.w700,
                          height: 1.3,
                        ),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 2),
                      Text(
                        widget.alert.sourceOrg,
                        style: TextStyle(
                          color: Colors.white.withValues(alpha: 0.8),
                          fontSize: 11,
                        ),
                      ),
                    ],
                  ),
                ),
                // Dismiss button
                GestureDetector(
                  onTap: widget.onDismiss,
                  child: Container(
                    padding: const EdgeInsets.all(4),
                    child: Icon(Icons.close,
                        color: Colors.white.withValues(alpha: 0.85), size: 18),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// ── Alert card widget ─────────────────────────────────────────────────────────

class _AlertCard extends StatelessWidget {
  final OfficialAlert alert;
  final VoidCallback  onTap;

  const _AlertCard({required this.alert, required this.onTap});

  String _localeTitle(String t) {
    if (!LanguageService.instance.isUrdu) return t;
    if (t.contains('Rainfall')) return 'شدید بارش سے متعلق ایڈوائزری';
    if (t.contains('Flood'))    return 'اچانک سیلاب کا خدشہ';
    if (t.contains('GLOF'))     return 'گلیشیر سیلاب کا خطرہ';
    if (t.contains('Landslide'))return 'لینڈ سلائیڈ الرٹ';
    return t;
  }

  String _localeOrg(String o) {
    if (!LanguageService.instance.isUrdu) return o;
    if (o.contains('Meteorological')) return 'محکمہ موسمیات پاکستان';
    if (o.contains('NDMA'))           return 'این ڈی ایم اے';
    if (o.contains('PDMA'))           return 'پی ڈی ایم اے KP';
    return o;
  }

  String _localeArea(String a) {
    if (!LanguageService.instance.isUrdu) return a;
    if (a.contains('Chitral')) return 'ضلع چترال';
    return a;
  }

  String _localeDesc(String d) {
    if (!LanguageService.instance.isUrdu) return d;
    if (d.contains('rain') || d.contains('monsoon') || d.contains('Heavy'))
      return 'شدید بارش کی وجہ سے مقامی ندی نالوں میں سیلابی خطرہ ہے۔';
    if (d.contains('flood') || d.contains('nullah'))
      return 'متوقع بارش کے باعث مقامی ندی نالوں میں اچانک سیلابی ریلوں کا خطرہ ہے۔';
    return d;
  }

  @override
  Widget build(BuildContext context) {
    final isHigh = alert.severity.toLowerCase() == 'high';
    final sevColor = isHigh ? AppColors.riskHigh : AppColors.riskModerate;
    final sevBg    = isHigh ? AppColors.riskHighBg : AppColors.riskModerateBg;

    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(16),
      child: Container(
        margin: const EdgeInsets.only(bottom: 14),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(16),
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
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Top row — badge + issued time
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 10, vertical: 4),
                        decoration: BoxDecoration(
                          color: sevBg,
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(
                              isHigh
                                  ? Icons.warning_amber_rounded
                                  : Icons.info_outline,
                              size: 13, color: sevColor,
                            ),
                            const SizedBox(width: 4),
                            Text(
                              Tr.t('official_warning'),
                              style: TextStyle(
                                fontSize: 11,
                                fontWeight: FontWeight.w700,
                                color: sevColor,
                              ),
                            ),
                          ],
                        ),
                      ),
                      Text(alert.issuedAgo, style: AppTextStyles.caption),
                    ],
                  ),

                  const SizedBox(height: 10),
                  Text(_localeTitle(alert.title),
                      style: AppTextStyles.cardTitle),
                  const SizedBox(height: 4),

                  // Source org
                  Row(children: [
                    const Icon(Icons.apartment,
                        size: 13, color: AppColors.textMuted),
                    const SizedBox(width: 4),
                    Flexible(
                      child: Text(_localeOrg(alert.sourceOrg),
                          style: AppTextStyles.caption,
                          overflow: TextOverflow.ellipsis),
                    ),
                  ]),

                  const SizedBox(height: 12),

                  // Severity + Area row
                  Row(
                    children: [
                      Expanded(
                        child: _MetaCol(
                          label: LanguageService.instance.isUrdu
                              ? 'شدت' : 'SEVERITY',
                          value: Tr.riskLevel(alert.severity),
                          valueColor: sevColor,
                        ),
                      ),
                      Expanded(
                        child: _MetaCol(
                          label: LanguageService.instance.isUrdu
                              ? 'علاقہ' : 'AREA',
                          value: _localeArea(alert.area),
                          valueColor: AppColors.textPrimary,
                        ),
                      ),
                    ],
                  ),

                  const SizedBox(height: 10),
                  Text(
                    _localeDesc(alert.description),
                    style: AppTextStyles.body.copyWith(fontSize: 13),
                    maxLines: 3,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),

            // AI risk assessment footer
            if (alert.aiRiskAssessment != null &&
                alert.aiRiskAssessment!.isNotEmpty)
              Container(
                padding: const EdgeInsets.all(14),
                decoration: const BoxDecoration(
                  color: AppColors.aiCardBg,
                  borderRadius: BorderRadius.vertical(
                      bottom: Radius.circular(16)),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(Icons.smart_toy_outlined,
                        size: 15, color: AppColors.aiAccent),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Text(
                        alert.aiRiskAssessment!,
                        style: const TextStyle(
                          fontSize: 12,
                          color: AppColors.textPrimary,
                          height: 1.4,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _MetaCol extends StatelessWidget {
  final String label;
  final String value;
  final Color  valueColor;

  const _MetaCol({
    required this.label,
    required this.value,
    required this.valueColor,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: AppTextStyles.sectionLabel),
        const SizedBox(height: 2),
        Text(
          value,
          style: TextStyle(
              fontWeight: FontWeight.w700,
              color: valueColor,
              fontSize: 13),
        ),
      ],
    );
  }
}
