import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/localization/app_localizations.dart';
import '../../core/providers/app_state_provider.dart';
import '../../core/providers/language_provider.dart';
import '../../core/theme/app_theme.dart';
import '../chat/chat_screen.dart';
import '../alerts/alerts_screen.dart';
import '../map/hazard_map_screen.dart';
import '../safety/safety_checklist_screen.dart';
import '../profile/profile_screen.dart';
import '../go_bag/go_bag_screen.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  int _selectedIndex = 0;

  // Non-const so we can pass the callback into _HomeTab
  late final List<Widget> _screens = [
    _HomeTab(onNavigate: _setTab),
    const ChatScreen(),
    const AlertsScreen(),
    const HazardMapScreen(),
    const SafetyChecklistScreen(),
    const GoBagScreen(),
  ];

  void _setTab(int index) => setState(() => _selectedIndex = index);

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);
    // Watch connectivity so the NavBar chip updates automatically
    context.watch<AppStateProvider>();

    return Scaffold(
      body: _screens[_selectedIndex],
      bottomNavigationBar: NavigationBar(
        selectedIndex: _selectedIndex,
        onDestinationSelected: _setTab,
        backgroundColor: Colors.white,
        indicatorColor: AppColors.primaryLight.withValues(alpha: 0.3),
        destinations: [
          NavigationDestination(
            icon: const Icon(Icons.home_outlined),
            selectedIcon: const Icon(Icons.home_rounded),
            label: loc.dashboard,
          ),
          NavigationDestination(
            icon: const Icon(Icons.chat_bubble_outline_rounded),
            selectedIcon: const Icon(Icons.chat_bubble_rounded),
            label: loc.chat,
          ),
          NavigationDestination(
            icon: const Icon(Icons.notifications_outlined),
            selectedIcon: const Icon(Icons.notifications_rounded),
            label: loc.alerts,
          ),
          NavigationDestination(
            icon: const Icon(Icons.map_outlined),
            selectedIcon: const Icon(Icons.map_rounded),
            label: loc.hazardMap,
          ),
          NavigationDestination(
            icon: const Icon(Icons.checklist_outlined),
            selectedIcon: const Icon(Icons.checklist_rounded),
            label: loc.safetyChecklist,
          ),
          NavigationDestination(
            icon: const Icon(Icons.backpack_outlined),
            selectedIcon: const Icon(Icons.backpack_rounded),
            label: 'Go Bag',
          ),
        ],
      ),
    );
  }
}

// ─── Home Tab ─────────────────────────────────────────────────────────────────

class _HomeTab extends StatelessWidget {
  /// Callback to switch the parent [DashboardScreen] tab index.
  final ValueChanged<int> onNavigate;

  const _HomeTab({required this.onNavigate});

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);
    final appState = context.watch<AppStateProvider>();
    final langProvider = context.watch<LanguageProvider>();

    return Scaffold(
      appBar: AppBar(
        title: Text(loc.appName),
        actions: [
          // Connectivity chip
          Padding(
            padding: const EdgeInsets.only(right: 8),
            child: Chip(
              avatar: Icon(
                appState.isOnline ? Icons.wifi : Icons.wifi_off,
                size: 14,
                color: appState.isOnline
                    ? AppColors.hazardLow
                    : AppColors.textMuted,
              ),
              label: Text(
                appState.isOnline ? loc.online : loc.offline,
                style: const TextStyle(fontSize: 11),
              ),
              backgroundColor: appState.isOnline
                  ? AppColors.hazardLow.withValues(alpha: 0.12)
                  : AppColors.textMuted.withValues(alpha: 0.12),
              padding: EdgeInsets.zero,
            ),
          ),
          // Profile
          IconButton(
            icon: const Icon(Icons.person_outline),
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => const ProfileScreen()),
            ),
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.symmetric(vertical: 16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Tagline banner
            Container(
              margin: const EdgeInsets.symmetric(horizontal: 16),
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [AppColors.primary, AppColors.primaryDark],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                borderRadius: BorderRadius.circular(16),
              ),
              child: Row(
                children: [
                  const Icon(Icons.offline_bolt_rounded,
                      color: Colors.white, size: 36),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          loc.appName,
                          style: const TextStyle(
                              color: Colors.white,
                              fontSize: 15,
                              fontWeight: FontWeight.w700),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          loc.tagline,
                          style: const TextStyle(
                              color: Colors.white70, fontSize: 12),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),

            // Quick Actions
            const _SectionHeader(title: 'Quick Actions'),
            GridView.count(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              crossAxisCount: 2,
              padding: const EdgeInsets.symmetric(horizontal: 12),
              mainAxisSpacing: 8,
              crossAxisSpacing: 8,
              childAspectRatio: 1.4,
              children: [
                _QuickActionCard(
                  icon: Icons.chat_bubble_rounded,
                  label: loc.chat,
                  color: AppColors.primary,
                  onTap: () => onNavigate(1),
                ),
                _QuickActionCard(
                  icon: Icons.map_rounded,
                  label: loc.hazardMap,
                  color: AppColors.hazardMedium,
                  onTap: () => onNavigate(3),
                ),
                _QuickActionCard(
                  icon: Icons.notifications_active_rounded,
                  label: loc.alerts,
                  color: AppColors.hazardHigh,
                  onTap: () => onNavigate(2),
                ),
                _QuickActionCard(
                  icon: Icons.checklist_rounded,
                  label: loc.safetyChecklist,
                  color: AppColors.primaryDark,
                  onTap: () => onNavigate(4),
                ),
                _QuickActionCard(
                  icon: Icons.backpack_rounded,
                  label: 'Go Bag',
                  color: AppColors.pmdColor,
                  onTap: () => onNavigate(5),
                ),
              ],
            ),
            const SizedBox(height: 24),

            // Hazard coverage
            const _SectionHeader(title: 'Hazard Coverage'),
            _HazardCoverageRow(loc: loc),
            const SizedBox(height: 24),

            // Language selector
            _SectionHeader(title: loc.language),
            _LanguageSelectorRow(provider: langProvider),
            const SizedBox(height: 24),

            // Disclaimer
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppColors.accent.withValues(alpha: 0.08),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(
                      color: AppColors.accent.withValues(alpha: 0.3)),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(Icons.info_outline,
                        color: AppColors.accent, size: 18),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'Not an official emergency alert system. '
                        'Always follow NDMA/PDMA directives.',
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                            color: AppColors.textDark.withValues(alpha: 0.75),
                            fontSize: 12),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),
          ],
        ),
      ),
    );
  }
}

// ─── Supporting widgets ───────────────────────────────────────────────────────

class _SectionHeader extends StatelessWidget {
  final String title;
  const _SectionHeader({required this.title});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Text(
        title,
        style: Theme.of(context)
            .textTheme
            .titleLarge
            ?.copyWith(fontSize: 15, color: AppColors.textMuted),
      ),
    );
  }
}

class _QuickActionCard extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color color;
  final VoidCallback onTap;

  const _QuickActionCard({
    required this.icon,
    required this.label,
    required this.color,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(icon, size: 32, color: color),
              const SizedBox(height: 8),
              Text(
                label,
                style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: color),
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _HazardCoverageRow extends StatelessWidget {
  final AppLocalizations loc;
  const _HazardCoverageRow({required this.loc});

  @override
  Widget build(BuildContext context) {
    final items = [
      (Icons.water_rounded,      loc.flood,      AppColors.primary),
      (Icons.thunderstorm_rounded, loc.flashFlood, AppColors.hazardMedium),
      (Icons.landslide_rounded,  loc.landslide,  AppColors.hazardHigh),
    ];
    return SizedBox(
      height: 80,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemCount: items.length,
        itemBuilder: (_, i) {
          final (icon, label, color) = items[i];
          return Container(
            width: 110,
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.08),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: color.withValues(alpha: 0.25)),
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(icon, color: color, size: 26),
                const SizedBox(height: 4),
                Text(
                  label,
                  style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: color),
                  textAlign: TextAlign.center,
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}

class _LanguageSelectorRow extends StatelessWidget {
  final LanguageProvider provider;
  const _LanguageSelectorRow({required this.provider});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 44,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemCount: LanguageProvider.supportedLanguages.length,
        itemBuilder: (_, i) {
          final lang = LanguageProvider.supportedLanguages[i];
          final isSelected = provider.languageCode == lang['code'];
          return GestureDetector(
            onTap: () => provider.setLanguage(lang['code']!),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              padding:
                  const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              decoration: BoxDecoration(
                color: isSelected ? AppColors.primary : Colors.white,
                borderRadius: BorderRadius.circular(22),
                border: Border.all(
                    color: AppColors.primary.withValues(alpha: 0.4)),
              ),
              child: Text(
                lang['label']!,
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: isSelected ? Colors.white : AppColors.primary,
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}
