/// Compatibility shim — delegates to the new LanguageService + AppTranslations.
/// Existing screens import this file; new screens use LanguageService directly.
library app_localizations;

import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'language_service.dart';
import 'app_translations.dart';

export 'language_service.dart';
export 'app_translations.dart';

class AppLocalizations {
  final Locale locale;
  AppLocalizations(this.locale);

  static AppLocalizations of(BuildContext context) {
    // Use the singleton LanguageService; locale from context as fallback
    return AppLocalizations(LanguageService.instance.locale);
  }

  static const List<Locale> supportedLocales = [
    Locale('en', 'US'),
    Locale('ur', 'PK'),
    Locale('ur', 'Latn'),
  ];

  static const List<LocalizationsDelegate> localizationsDelegates = [
    _AppLocalizationsDelegate(),
    GlobalMaterialLocalizations.delegate,
    GlobalWidgetsLocalizations.delegate,
    GlobalCupertinoLocalizations.delegate,
  ];

  // ── String helpers ────────────────────────────────────────────────────────
  String _t(String key) => Tr.t(key);

  String get appName         => _t('app_name');
  String get tagline         => _t('tagline');
  String get login           => _t('login');
  String get signup          => _t('signup');
  String get logout          => _t('logout');
  String get email           => _t('email');
  String get password        => _t('password');
  String get name            => _t('name');
  String get continueOffline => _t('continue_offline');
  String get dashboard       => _t('dashboard');
  String get chat            => _t('chat');
  String get alerts          => _t('alerts');
  String get hazardMap       => _t('hazard_map');
  String get safetyChecklist => _t('safety_checklist');
  String get profile         => _t('profile');
  String get online          => _t('online');
  String get offline         => _t('offline');
  String get syncing         => _t('syncing');
  String get lastSynced      => _t('last_synced');
  String get syncNow         => _t('sync_now');
  String get hazardLevel     => _t('hazard_level');
  String get high            => _t('high');
  String get medium          => _t('medium');
  String get low             => _t('low');
  String get unknown         => _t('unknown');
  String get indicatorDisclaimer => _t('indicator_disclaimer');
  String get source          => _t('source');
  String get evidenceLevel   => _t('evidence_level');
  String get typeQuestion    => _t('type_question');
  String get ask             => _t('ask');
  String get noResults       => _t('no_results');
  String get loading         => _t('loading');
  String get error           => _t('error');
  String get retry           => _t('retry');
  String get language        => _t('language');
  String get settings        => _t('settings');
  String get flood           => _t('flood');
  String get flashFlood      => _t('flash_flood');
  String get landslide       => _t('landslide');
  String get checklistGoBag  => _t('checklist_go_bag');
  String get checklistEvacuation => _t('checklist_evacuation');
  String get checklistFlood  => _t('checklist_flood');
  String get checklistLandslide => _t('checklist_landslide');
  String get myLocation      => _t('my_location');
  String get detectingLocation => _t('detecting_location');
  String get locationUnavailable => _t('location_unavailable');
  String get noAlerts        => _t('no_alerts');
  String get officialSource  => _t('official_source');
  String get getStarted      => _t('get_started');
  String get next            => _t('next');
  String get skip            => _t('skip');
  String get onboardingTitle1 => _t('onboarding_title_1');
  String get onboardingBody1  => _t('onboarding_body_1');
  String get onboardingTitle2 => _t('onboarding_title_2');
  String get onboardingBody2  => _t('onboarding_body_2');
  String get onboardingTitle3 => _t('onboarding_title_3');
  String get onboardingBody3  => _t('onboarding_body_3');

  String translate(String key) => _t(key);

  String hazardLevelLabel(String level) {
    switch (level.toUpperCase()) {
      case 'HIGH':   return high;
      case 'MEDIUM': return medium;
      case 'LOW':    return low;
      default:       return unknown;
    }
  }
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  bool isSupported(Locale locale) =>
      ['en', 'ur'].contains(locale.languageCode);

  @override
  Future<AppLocalizations> load(Locale locale) async =>
      AppLocalizations(locale);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}
