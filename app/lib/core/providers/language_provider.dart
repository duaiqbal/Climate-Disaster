/// Compatibility shim — delegates to LanguageService.
/// Existing screens that use LanguageProvider via Provider still work.
library language_provider;

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../localization/language_service.dart';

export '../localization/language_service.dart';

class LanguageProvider extends ChangeNotifier {
  String _code = 'en';

  LanguageProvider(String initialCode) {
    _code = initialCode;
    LanguageService.instance.currentLanguage.addListener(_onServiceChange);
  }

  void _onServiceChange() {
    final svc = LanguageService.instance;
    final newCode = svc.isUrdu
        ? 'ur'
        : svc.isRomanUrdu
            ? 'ru'
            : 'en';
    if (newCode != _code) {
      _code = newCode;
      notifyListeners();
    }
  }

  String get languageCode => _code;
  bool get isUrdu       => _code == 'ur';
  bool get isRomanUrdu  => _code == 'ru';
  bool get isEnglish    => _code == 'en';

  TextDirection get textDirection =>
      _code == 'ur' ? TextDirection.rtl : TextDirection.ltr;

  String get languageLabel {
    switch (_code) {
      case 'ur': return '\u0627\u0631\u062F\u0648';
      case 'ru': return 'Roman Urdu';
      default:   return 'English';
    }
  }

  Future<void> setLanguage(String code) async {
    _code = code;
    // Sync back to LanguageService
    final lang = code == 'ur'
        ? AppLanguage.urdu
        : code == 'ru'
            ? AppLanguage.romanUrdu
            : AppLanguage.english;
    LanguageService.instance.setLanguage(lang);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('language', code);
    notifyListeners();
  }

  static const List<Map<String, String>> supportedLanguages = [
    {'code': 'en', 'label': 'English'},
    {'code': 'ur', 'label': '\u0627\u0631\u062F\u0648'},
    {'code': 'ru', 'label': 'Roman Urdu'},
  ];

  @override
  void dispose() {
    LanguageService.instance.currentLanguage.removeListener(_onServiceChange);
    super.dispose();
  }
}
