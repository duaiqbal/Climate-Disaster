import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../core/local_db/database_helper.dart';
import '../../core/localization/app_localizations.dart';
import '../../core/services/auth_service.dart';
import '../../core/providers/app_state_provider.dart';
import '../../core/providers/language_provider.dart';
import '../../core/theme/app_theme.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  String _name = '';
  String _email = '';
  Map<String, dynamic>? _packageMeta;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final prefs = await SharedPreferences.getInstance();
    // getPackageMeta() is now null-safe and will not throw
    final meta = await DatabaseHelper.instance.getPackageMeta();
    if (mounted) {
      setState(() {
        _name = prefs.getString('user_name') ?? 'Guest';
        _email = prefs.getString('user_email') ?? '';
        _packageMeta = meta;
      });
    }
  }

  Future<void> _logout() async {
    await AuthService.logout();
    if (!mounted) return;
    Navigator.pushNamedAndRemoveUntil(context, '/login', (_) => false);
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);
    final langProvider = context.watch<LanguageProvider>();
    final appState = context.watch<AppStateProvider>();

    return Scaffold(
      appBar: AppBar(title: Text(loc.profile)),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Avatar + name
            Center(
              child: Column(
                children: [
                  CircleAvatar(
                    radius: 40,
                    backgroundColor: AppColors.primaryLight.withValues(alpha: 0.3),
                    child: Text(
                      _name.isNotEmpty ? _name[0].toUpperCase() : 'G',
                      style: const TextStyle(
                          fontSize: 32,
                          fontWeight: FontWeight.w700,
                          color: AppColors.primary),
                    ),
                  ),
                  const SizedBox(height: 10),
                  Text(_name, style: Theme.of(context).textTheme.titleLarge),
                  if (_email.isNotEmpty)
                    Text(_email,
                        style: const TextStyle(
                            color: AppColors.textMuted, fontSize: 13)),
                ],
              ),
            ),
            const SizedBox(height: 28),

            // Language section
            _SectionTitle(loc.language),
            Card(
              child: Column(
                children: LanguageProvider.supportedLanguages.map((lang) {
                  final isSelected =
                      langProvider.languageCode == lang['code'];
                  return InkWell(
                    onTap: () => langProvider.setLanguage(lang['code']!),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 16, vertical: 12),
                      child: Row(
                        children: [
                          Icon(
                            isSelected
                                ? Icons.radio_button_checked
                                : Icons.radio_button_unchecked,
                            color: isSelected
                                ? AppColors.primary
                                : AppColors.textMuted,
                            size: 20,
                          ),
                          const SizedBox(width: 12),
                          Text(lang['label']!,
                              style: TextStyle(
                                fontSize: 14,
                                color: isSelected
                                    ? AppColors.primary
                                    : AppColors.textDark,
                                fontWeight: isSelected
                                    ? FontWeight.w600
                                    : FontWeight.normal,
                              )),
                        ],
                      ),
                    ),
                  );
                }).toList(),
              ),
            ),
            const SizedBox(height: 16),

            // Connectivity
            _SectionTitle('Status'),
            Card(
              child: ListTile(
                leading: Icon(
                  appState.isOnline ? Icons.wifi : Icons.wifi_off,
                  color: appState.isOnline
                      ? AppColors.hazardLow
                      : AppColors.textMuted,
                ),
                title: Text(appState.isOnline ? loc.online : loc.offline),
                subtitle: appState.lastSyncedAt != null
                    ? Text(
                        '${loc.lastSynced}: '
                        '${appState.lastSyncedAt!.toLocal().toString().split('.').first}',
                        style: const TextStyle(fontSize: 12))
                    : null,
              ),
            ),
            const SizedBox(height: 16),

            // Package info — only shown when package_meta exists
            if (_packageMeta != null) ...[
              _SectionTitle('Offline Package'),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    children: [
                      _MetaRow('Version',
                          _packageMeta!['version']?.toString() ?? 'n/a'),
                      _MetaRow('Built',
                          _packageMeta!['built_at']?.toString() ?? 'n/a'),
                      _MetaRow('Chunks',
                          _packageMeta!['chunk_count']?.toString() ?? 'n/a'),
                      _MetaRow('Sources',
                          _packageMeta!['source_docs']?.toString() ?? 'n/a'),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),
            ],

            // Logout
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                icon: const Icon(Icons.logout_rounded,
                    color: AppColors.hazardHigh),
                label: Text(loc.logout,
                    style: const TextStyle(color: AppColors.hazardHigh)),
                onPressed: _logout,
                style: OutlinedButton.styleFrom(
                  side: const BorderSide(color: AppColors.hazardHigh),
                  padding: const EdgeInsets.symmetric(vertical: 14),
                ),
              ),
            ),
            const SizedBox(height: 24),

            // Attribution — clean UTF-8
            const Center(
              child: Text(
                'Data: NDMA \u00B7 PDMA KP \u00B7 PMD \u00B7 Copernicus DEM \u00B7 OpenStreetMap\n'
                'MIT License \u00B7 Tooba Iqbal, Kiran Shams, Manahill Khitab',
                style: TextStyle(
                    fontSize: 10, color: AppColors.textMuted, height: 1.6),
                textAlign: TextAlign.center,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  final String title;
  const _SectionTitle(this.title);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(left: 4, bottom: 6),
      child: Text(title,
          style: const TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w700,
              color: AppColors.textMuted,
              letterSpacing: 0.8)),
    );
  }
}

class _MetaRow extends StatelessWidget {
  final String label;
  final String value;
  const _MetaRow(this.label, this.value);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        children: [
          Text(label,
              style: const TextStyle(
                  fontSize: 12, color: AppColors.textMuted)),
          const Spacer(),
          Text(value,
              style: const TextStyle(
                  fontSize: 12, fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }
}
