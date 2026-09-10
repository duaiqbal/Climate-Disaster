import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Supported languages: English (en), Urdu (ur), Roman Urdu (ru = custom code).
class LanguageProvider extends ChangeNotifier {
  String _languageCode;

  LanguageProvider(this._languageCode);

  String get languageCode => _languageCode;

  bool get isUrdu => _languageCode == 'ur';
  bool get isRomanUrdu => _languageCode == 'ru';
  bool get isEnglish => _languageCode == 'en';

  /// Text direction — Urdu is RTL; English and Roman Urdu are LTR.
  TextDirection get textDirection =>
      _languageCode == 'ur' ? TextDirection.rtl : TextDirection.ltr;

  /// Human-readable label for current language.
  String get languageLabel {
    switch (_languageCode) {
      case 'ur':
        return 'اردو';
      case 'ru':
        return 'Roman Urdu';
      default:
        return 'English';
    }
  }

  Future<void> setLanguage(String code) async {
    _languageCode = code;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('language', code);
    notifyListeners();
  }

  static const List<Map<String, String>> supportedLanguages = [
    {'code': 'en', 'label': 'English'},
    {'code': 'ur', 'label': 'اردو'},
    {'code': 'ru', 'label': 'Roman Urdu'},
  ];
}
