// app/test/widget_test.dart
// =========================
// Real Flutter widget and unit tests for Disaster DSS.
// Tests are written to work without a running backend (offline-first principle).

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:disaster_dss/core/localization/app_localizations.dart';
import 'package:disaster_dss/core/providers/language_provider.dart';
import 'package:disaster_dss/core/providers/app_state_provider.dart';
import 'package:disaster_dss/core/retrieval/roman_urdu_normalizer.dart';
import 'package:disaster_dss/core/rules_engine/hazard_rules.dart';
import 'package:disaster_dss/core/services/auth_service.dart';
import 'package:disaster_dss/features/onboarding/onboarding_screen.dart';
import 'package:disaster_dss/features/auth/login_screen.dart';

// ── Helper ────────────────────────────────────────────────────────────────────

Widget _wrap(Widget child, {String lang = 'en'}) {
  return MultiProvider(
    providers: [
      ChangeNotifierProvider(create: (_) => LanguageProvider(lang)),
      ChangeNotifierProvider(create: (_) => AppStateProvider()),
    ],
    child: MaterialApp(
      locale: Locale(lang),
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: child,
    ),
  );
}

// ── Unit tests: HazardRules ───────────────────────────────────────────────────

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('HazardRules — deterministic classifier', () {
    test('HIGH flood: river < 0.5 km, elevation < 2000 m', () {
      final result = HazardRules.classify(
          slopeDeg: 10, riverDistKm: 0.3, elevationM: 1500);
      expect(result.floodLevel, HazardLevel.high);
      expect(result.overallLevel, HazardLevel.high);
    });

    test('MEDIUM flood: river 0.5–1.5 km', () {
      final result = HazardRules.classify(
          slopeDeg: 5, riverDistKm: 1.0, elevationM: 1500);
      expect(result.floodLevel, HazardLevel.medium);
    });

    test('LOW flood: river > 1.5 km, low slope', () {
      final result = HazardRules.classify(
          slopeDeg: 5, riverDistKm: 2.0, elevationM: 2500);
      expect(result.floodLevel, HazardLevel.low);
      expect(result.landslideLevel, HazardLevel.low);
      expect(result.overallLevel, HazardLevel.low);
    });

    test('HIGH landslide: slope > 30°', () {
      final result = HazardRules.classify(
          slopeDeg: 35, riverDistKm: 3.0, elevationM: 3000);
      expect(result.landslideLevel, HazardLevel.high);
      expect(result.overallLevel, HazardLevel.high);
    });

    test('MEDIUM landslide: slope 15–30°', () {
      final result = HazardRules.classify(
          slopeDeg: 20, riverDistKm: 3.0, elevationM: 3000);
      expect(result.landslideLevel, HazardLevel.medium);
    });

    test('Worst-case combination: flood LOW + landslide HIGH = overall HIGH', () {
      final result = HazardRules.classify(
          slopeDeg: 35, riverDistKm: 2.0, elevationM: 3000);
      expect(result.overallLevel, HazardLevel.high);
    });

    test('Disclaimer is always present', () {
      expect(HazardAssessment.disclaimer, isNotEmpty);
      expect(HazardAssessment.disclaimer.toLowerCase(), contains('not'));
    });

    test('Contributing factors populated when risk exists', () {
      final result = HazardRules.classify(
          slopeDeg: 35, riverDistKm: 0.3, elevationM: 1500);
      expect(result.contributingFactors, isNotEmpty);
    });
  });

  // ── Unit tests: RomanUrduNormalizer ────────────────────────────────────────

  group('RomanUrduNormalizer', () {
    test('expands flood variants', () {
      final expanded = RomanUrduNormalizer.expandQuery('selab');
      expect(expanded, contains('selab'));
      expect(expanded.length, greaterThan(1));
    });

    test('auto-detects Roman Urdu', () {
      expect(RomanUrduNormalizer.isLikelyRomanUrdu('selab se bachao'), isTrue);
      expect(RomanUrduNormalizer.isLikelyRomanUrdu('what is the weather'), isFalse);
    });

    test('returns original token when not in variant map', () {
      final expanded = RomanUrduNormalizer.expandQuery('unknown_xyz');
      expect(expanded, contains('unknown_xyz'));
    });

    test('expandQuery on multi-word query', () {
      final expanded = RomanUrduNormalizer.expandQuery('flood mein bachao');
      expect(expanded, isNotEmpty);
      expect(expanded.length, greaterThan(2));
    });
  });

  // ── Unit tests: AuthException ──────────────────────────────────────────────

  group('AuthException', () {
    test('isUnauthorized true for 401', () {
      const e = AuthException('Bad credentials', 401);
      expect(e.isUnauthorized, isTrue);
      expect(e.isForbidden, isFalse);
    });

    test('isRateLimited true for 429', () {
      const e = AuthException('Too many requests', 429);
      expect(e.isRateLimited, isTrue);
    });

    test('isServerError true for 500', () {
      const e = AuthException('Server error', 500);
      expect(e.isServerError, isTrue);
    });

    test('toString returns message', () {
      const e = AuthException('Test message', 401);
      expect(e.toString(), 'Test message');
    });
  });

  // ── Widget tests: Onboarding ───────────────────────────────────────────────

  group('OnboardingScreen', () {
    testWidgets('renders first page title', (tester) async {
      SharedPreferences.setMockInitialValues({});
      await tester.pumpWidget(_wrap(const OnboardingScreen()));
      await tester.pump();
      // Should show some onboarding content
      expect(find.byType(PageView), findsOneWidget);
    });

    testWidgets('has navigation controls', (tester) async {
      SharedPreferences.setMockInitialValues({});
      await tester.pumpWidget(_wrap(const OnboardingScreen()));
      await tester.pump();
      // Should have a forward button
      expect(find.byType(ElevatedButton), findsAtLeastNWidgets(1));
    });
  });

  // ── Widget tests: Login ────────────────────────────────────────────────────

  group('LoginScreen', () {
    testWidgets('renders email and password fields', (tester) async {
      SharedPreferences.setMockInitialValues({});
      await tester.pumpWidget(_wrap(const LoginScreen()));
      await tester.pump();
      expect(find.byType(TextFormField), findsAtLeastNWidgets(2));
    });

    testWidgets('renders login button', (tester) async {
      SharedPreferences.setMockInitialValues({});
      await tester.pumpWidget(_wrap(const LoginScreen()));
      await tester.pump();
      expect(find.byType(ElevatedButton), findsAtLeastNWidgets(1));
    });

    testWidgets('renders Continue Offline button', (tester) async {
      SharedPreferences.setMockInitialValues({});
      await tester.pumpWidget(_wrap(const LoginScreen()));
      await tester.pump();
      expect(find.byType(OutlinedButton), findsOneWidget);
    });

    testWidgets('validation fails on empty fields', (tester) async {
      SharedPreferences.setMockInitialValues({});
      await tester.pumpWidget(_wrap(const LoginScreen()));
      await tester.pump();
      // Tap login button without filling fields
      final loginBtn = find.byType(ElevatedButton).first;
      await tester.tap(loginBtn);
      await tester.pump();
      // Validation error text appears
      expect(find.text('Required'), findsAtLeastNWidgets(1));
    });
  });

  // ── Widget tests: Language switching ──────────────────────────────────────

  group('LanguageProvider', () {
    test('initial language is set from constructor', () {
      final provider = LanguageProvider('ur');
      expect(provider.languageCode, 'ur');
      expect(provider.isUrdu, isTrue);
    });

    test('setLanguage updates languageCode', () async {
      SharedPreferences.setMockInitialValues({});
      final provider = LanguageProvider('en');
      await provider.setLanguage('ru');
      expect(provider.languageCode, 'ru');
      expect(provider.isRomanUrdu, isTrue);
    });

    test('textDirection is RTL for Urdu', () {
      final provider = LanguageProvider('ur');
      expect(provider.textDirection, TextDirection.rtl);
    });

    test('textDirection is LTR for English and Roman Urdu', () {
      expect(LanguageProvider('en').textDirection, TextDirection.ltr);
      expect(LanguageProvider('ru').textDirection, TextDirection.ltr);
    });
  });
}
