import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

/// Simple in-app localizations — no generated ARB files needed for offline use.
/// Covers English (en), Urdu (ur), and Roman Urdu (ru — custom locale code).
class AppLocalizations {
  final Locale locale;
  AppLocalizations(this.locale);

  static AppLocalizations of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations)!;
  }

  static const List<Locale> supportedLocales = [
    Locale('en'),
    Locale('ur'),
    Locale('ru'), // Roman Urdu — custom
  ];

  static const List<LocalizationsDelegate> localizationsDelegates = [
    _AppLocalizationsDelegate(),
    GlobalMaterialLocalizations.delegate,
    GlobalWidgetsLocalizations.delegate,
    GlobalCupertinoLocalizations.delegate,
  ];

  // ─── String map ───────────────────────────────────────────────────────────
  static const Map<String, Map<String, String>> _strings = {
    'en': {
      'app_name': 'Disaster DSS – Chitral',
      'tagline': 'Offline-first disaster decision support',
      'login': 'Login',
      'signup': 'Sign Up',
      'logout': 'Logout',
      'email': 'Email',
      'password': 'Password',
      'name': 'Full Name',
      'continue_offline': 'Continue Offline',
      'dashboard': 'Dashboard',
      'chat': 'Ask a Question',
      'alerts': 'Alerts',
      'hazard_map': 'Hazard Map',
      'safety_checklist': 'Safety Checklist',
      'profile': 'Profile',
      'online': 'Online',
      'offline': 'Offline',
      'syncing': 'Syncing…',
      'last_synced': 'Last synced',
      'sync_now': 'Sync Now',
      'hazard_level': 'Hazard Level',
      'high': 'HIGH',
      'medium': 'MEDIUM',
      'low': 'LOW',
      'unknown': 'Unknown',
      'indicator_disclaimer':
          'This is a coarse indicator based on slope & river proximity — not a validated prediction.',
      'source': 'Source',
      'evidence_level': 'Evidence',
      'type_question': 'Type your question…',
      'ask': 'Ask',
      'no_results': 'No results found. Try different keywords.',
      'loading': 'Loading…',
      'error': 'An error occurred.',
      'retry': 'Retry',
      'language': 'Language',
      'settings': 'Settings',
      'flood': 'Flood',
      'flash_flood': 'Flash Flood',
      'landslide': 'Landslide',
      'checklist_go_bag': 'Go-Bag Checklist',
      'checklist_evacuation': 'Evacuation Plan',
      'checklist_flood': 'Flood Safety',
      'checklist_landslide': 'Landslide Safety',
      'my_location': 'My Location',
      'detecting_location': 'Detecting location…',
      'location_unavailable': 'Location unavailable.',
      'no_alerts': 'No active alerts at this time.',
      'official_source': 'Official Source',
      'onboarding_title_1': 'Stay Safe, Stay Informed',
      'onboarding_body_1':
          'Access verified official disaster guidance for Chitral — even without internet.',
      'onboarding_title_2': 'Know Your Hazard',
      'onboarding_body_2':
          'GPS-based hazard indicator shows your flood & landslide exposure based on terrain data.',
      'onboarding_title_3': 'Your Language',
      'onboarding_body_3':
          'Full support for English, Urdu, and Roman Urdu.',
      'get_started': 'Get Started',
      'next': 'Next',
      'skip': 'Skip',
    },
    'ur': {
      'app_name': 'ڈیزاسٹر DSS – چترال',
      'tagline': 'آف لائن ڈیزاسٹر فیصلہ سپورٹ سسٹم',
      'login': 'لاگ ان',
      'signup': 'سائن اپ',
      'logout': 'لاگ آؤٹ',
      'email': 'ای میل',
      'password': 'پاس ورڈ',
      'name': 'پورا نام',
      'continue_offline': 'آف لائن جاری رکھیں',
      'dashboard': 'ڈیش بورڈ',
      'chat': 'سوال پوچھیں',
      'alerts': 'الرٹس',
      'hazard_map': 'خطرے کا نقشہ',
      'safety_checklist': 'حفاظتی فہرست',
      'profile': 'پروفائل',
      'online': 'آن لائن',
      'offline': 'آف لائن',
      'syncing': 'مطابقت ہو رہی ہے…',
      'last_synced': 'آخری مطابقت',
      'sync_now': 'ابھی مطابقت کریں',
      'hazard_level': 'خطرے کی سطح',
      'high': 'زیادہ',
      'medium': 'درمیانہ',
      'low': 'کم',
      'unknown': 'نامعلوم',
      'indicator_disclaimer':
          'یہ ڈھلوان اور دریا کی قربت پر مبنی ایک اشارہ ہے — تصدیق شدہ پیشگوئی نہیں۔',
      'source': 'ماخذ',
      'evidence_level': 'ثبوت',
      'type_question': 'اپنا سوال لکھیں…',
      'ask': 'پوچھیں',
      'no_results': 'کوئی نتیجہ نہیں ملا۔ مختلف الفاظ آزمائیں۔',
      'loading': 'لوڈ ہو رہا ہے…',
      'error': 'ایک خرابی پیش آئی۔',
      'retry': 'دوبارہ کوشش',
      'language': 'زبان',
      'settings': 'ترتیبات',
      'flood': 'سیلاب',
      'flash_flood': 'اچانک سیلاب',
      'landslide': 'لینڈ سلائیڈ',
      'checklist_go_bag': 'جانے کا بیگ',
      'checklist_evacuation': 'انخلاء کا منصوبہ',
      'checklist_flood': 'سیلاب سے بچاؤ',
      'checklist_landslide': 'لینڈ سلائیڈ سے بچاؤ',
      'my_location': 'میری جگہ',
      'detecting_location': 'جگہ معلوم ہو رہی ہے…',
      'location_unavailable': 'جگہ دستیاب نہیں۔',
      'no_alerts': 'اس وقت کوئی فعال الرٹ نہیں۔',
      'official_source': 'سرکاری ماخذ',
      'onboarding_title_1': 'محفوظ رہیں، باخبر رہیں',
      'onboarding_body_1':
          'انٹرنیٹ کے بغیر بھی چترال کے لیے سرکاری آفات کی رہنمائی حاصل کریں۔',
      'onboarding_title_2': 'اپنا خطرہ جانیں',
      'onboarding_body_2':
          'GPS پر مبنی خطرے کا اشارہ زمین کے ڈیٹا سے آپ کا سیلاب و لینڈ سلائیڈ خطرہ بتاتا ہے۔',
      'onboarding_title_3': 'آپ کی زبان',
      'onboarding_body_3': 'انگریزی، اردو اور رومن اردو مکمل سپورٹ کے ساتھ۔',
      'get_started': 'شروع کریں',
      'next': 'اگلا',
      'skip': 'چھوڑیں',
    },
    'ru': {
      'app_name': 'Disaster DSS – Chitral',
      'tagline': 'Offline disaster decision support',
      'login': 'Login',
      'signup': 'Register',
      'logout': 'Logout',
      'email': 'Email',
      'password': 'Password',
      'name': 'Poora naam',
      'continue_offline': 'Offline jaari rakhen',
      'dashboard': 'Dashboard',
      'chat': 'Sawal poochhen',
      'alerts': 'Alerts',
      'hazard_map': 'Khatra Naqsha',
      'safety_checklist': 'Hifazati List',
      'profile': 'Profile',
      'online': 'Online',
      'offline': 'Offline',
      'syncing': 'Sync ho raha hai…',
      'last_synced': 'Aakhri sync',
      'sync_now': 'Abhi sync karen',
      'hazard_level': 'Khatra Level',
      'high': 'ZYADA',
      'medium': 'DARMIYANA',
      'low': 'KAM',
      'unknown': 'Maloom nahi',
      'indicator_disclaimer':
          'Yeh sirf ek ishara hai — slope aur darya ki qurbat ka — koi confirmed prediction nahi.',
      'source': 'Maakhaz',
      'evidence_level': 'Saboot',
      'type_question': 'Sawal likhen…',
      'ask': 'Poochhen',
      'no_results': 'Koi nateeja nahi mila. Doosre alfaaz try karen.',
      'loading': 'Load ho raha hai…',
      'error': 'Kuch ghalat hua.',
      'retry': 'Dobara koshish',
      'language': 'Zubaan',
      'settings': 'Settings',
      'flood': 'Saib / Flood',
      'flash_flood': 'Achanak Saib',
      'landslide': 'Zameeni Khiskaao',
      'checklist_go_bag': 'Go-Bag List',
      'checklist_evacuation': 'Nikalne ka plan',
      'checklist_flood': 'Flood Safety',
      'checklist_landslide': 'Landslide Safety',
      'my_location': 'Meri jagah',
      'detecting_location': 'Jagah maloom ho rahi hai…',
      'location_unavailable': 'Jagah dastiyaab nahi.',
      'no_alerts': 'Filhal koi alert nahi.',
      'official_source': 'Sarkari Maakhaz',
      'onboarding_title_1': 'Mehfooz Rahen, Baakhabar Rahen',
      'onboarding_body_1':
          'Internet ke baghair bhi Chitral ke liye sarkari aafat ki rahnumaai haasil karen.',
      'onboarding_title_2': 'Apna Khatra Jaanein',
      'onboarding_body_2':
          'GPS se khatra level bataata hai — zameen aur darya ka faasla dekh ke.',
      'onboarding_title_3': 'Aapki Zubaan',
      'onboarding_body_3':
          'English, Urdu aur Roman Urdu — tino mein kaam karta hai.',
      'get_started': 'Shuru Karen',
      'next': 'Agla',
      'skip': 'Skip',
    },
  };

  String translate(String key) {
    final lang = locale.languageCode;
    return _strings[lang]?[key] ?? _strings['en']?[key] ?? key;
  }

  String get appName => translate('app_name');
  String get tagline => translate('tagline');
  String get login => translate('login');
  String get signup => translate('signup');
  String get logout => translate('logout');
  String get email => translate('email');
  String get password => translate('password');
  String get name => translate('name');
  String get continueOffline => translate('continue_offline');
  String get dashboard => translate('dashboard');
  String get chat => translate('chat');
  String get alerts => translate('alerts');
  String get hazardMap => translate('hazard_map');
  String get safetyChecklist => translate('safety_checklist');
  String get profile => translate('profile');
  String get online => translate('online');
  String get offline => translate('offline');
  String get syncing => translate('syncing');
  String get lastSynced => translate('last_synced');
  String get syncNow => translate('sync_now');
  String get hazardLevel => translate('hazard_level');
  String get high => translate('high');
  String get medium => translate('medium');
  String get low => translate('low');
  String get unknown => translate('unknown');
  String get indicatorDisclaimer => translate('indicator_disclaimer');
  String get source => translate('source');
  String get evidenceLevel => translate('evidence_level');
  String get typeQuestion => translate('type_question');
  String get ask => translate('ask');
  String get noResults => translate('no_results');
  String get loading => translate('loading');
  String get error => translate('error');
  String get retry => translate('retry');
  String get language => translate('language');
  String get settings => translate('settings');
  String get flood => translate('flood');
  String get flashFlood => translate('flash_flood');
  String get landslide => translate('landslide');
  String get checklistGoBag => translate('checklist_go_bag');
  String get checklistEvacuation => translate('checklist_evacuation');
  String get checklistFlood => translate('checklist_flood');
  String get checklistLandslide => translate('checklist_landslide');
  String get myLocation => translate('my_location');
  String get detectingLocation => translate('detecting_location');
  String get locationUnavailable => translate('location_unavailable');
  String get noAlerts => translate('no_alerts');
  String get officialSource => translate('official_source');
  String get getStarted => translate('get_started');
  String get next => translate('next');
  String get skip => translate('skip');

  // Onboarding
  String get onboardingTitle1 => translate('onboarding_title_1');
  String get onboardingBody1 => translate('onboarding_body_1');
  String get onboardingTitle2 => translate('onboarding_title_2');
  String get onboardingBody2 => translate('onboarding_body_2');
  String get onboardingTitle3 => translate('onboarding_title_3');
  String get onboardingBody3 => translate('onboarding_body_3');

  // Hazard helpers
  String hazardLevelLabel(String level) {
    switch (level.toUpperCase()) {
      case 'HIGH':
        return high;
      case 'MEDIUM':
        return medium;
      case 'LOW':
        return low;
      default:
        return unknown;
    }
  }
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  bool isSupported(Locale locale) =>
      ['en', 'ur', 'ru'].contains(locale.languageCode);

  @override
  Future<AppLocalizations> load(Locale locale) async =>
      AppLocalizations(locale);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}
