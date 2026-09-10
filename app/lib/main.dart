import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'core/theme/app_theme.dart';
import 'core/local_db/database_helper.dart';
import 'core/localization/app_localizations.dart';
import 'core/providers/app_state_provider.dart';
import 'core/providers/language_provider.dart';

import 'features/onboarding/onboarding_screen.dart';
import 'features/auth/login_screen.dart';
import 'features/auth/signup_screen.dart';
import 'features/dashboard/dashboard_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Portrait lock — mobile only (web ignores this gracefully)
  if (!kIsWeb) {
    await SystemChrome.setPreferredOrientations([
      DeviceOrientation.portraitUp,
      DeviceOrientation.portraitDown,
    ]);
  }

  // SQLite not supported on web — skip DB init, app uses backend API instead
  if (!kIsWeb) {
    await DatabaseHelper.instance.init();
  }

  final prefs = await SharedPreferences.getInstance();
  final bool seenOnboarding = prefs.getBool('seen_onboarding') ?? false;
  final bool isLoggedIn    = prefs.getBool('is_logged_in')    ?? false;
  final String savedLang   = prefs.getString('language')      ?? 'en';

  runApp(
    MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => LanguageProvider(savedLang)),
        ChangeNotifierProvider(create: (_) => AppStateProvider()),
      ],
      child: DisasterDSSApp(
        initialRoute: seenOnboarding
            ? (isLoggedIn ? '/dashboard' : '/login')
            : '/onboarding',
      ),
    ),
  );
}

class DisasterDSSApp extends StatelessWidget {
  final String initialRoute;
  const DisasterDSSApp({super.key, required this.initialRoute});

  @override
  Widget build(BuildContext context) {
    final languageProvider = context.watch<LanguageProvider>();

    return MaterialApp(
      title: 'Disaster DSS – Chitral',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.lightTheme,
      darkTheme: AppTheme.darkTheme,
      themeMode: ThemeMode.system,

      // Locale / i18n
      locale: Locale(languageProvider.languageCode),
      supportedLocales: AppLocalizations.supportedLocales,
      localizationsDelegates: AppLocalizations.localizationsDelegates,

      initialRoute: initialRoute,
      routes: {
        '/onboarding': (_) => const OnboardingScreen(),
        '/login': (_) => const LoginScreen(),
        '/signup': (_) => const SignupScreen(),
        '/dashboard': (_) => const DashboardScreen(),
      },
    );
  }
}
