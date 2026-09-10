import 'package:flutter/material.dart';

/// Disaster DSS brand colours — warm but high-contrast for field use.
class AppColors {
  // Primary — deep teal (trust / official)
  static const Color primary = Color(0xFF00695C);
  static const Color primaryLight = Color(0xFF4DB6AC);
  static const Color primaryDark = Color(0xFF004D40);

  // Accent — amber (urgency / alerts)
  static const Color accent = Color(0xFFFFA000);
  static const Color accentLight = Color(0xFFFFCC02);

  // Hazard levels
  static const Color hazardHigh = Color(0xFFD32F2F);
  static const Color hazardMedium = Color(0xFFF57C00);
  static const Color hazardLow = Color(0xFF388E3C);
  static const Color hazardUnknown = Color(0xFF757575);

  // Surfaces
  static const Color surface = Color(0xFFF5F5F5);
  static const Color surfaceDark = Color(0xFF1E1E1E);
  static const Color cardLight = Colors.white;
  static const Color cardDark = Color(0xFF2C2C2C);

  // Text
  static const Color textDark = Color(0xFF212121);
  static const Color textMuted = Color(0xFF757575);
  static const Color textLight = Color(0xFFFAFAFA);

  // Source badge colours
  static const Color ndmaColor = Color(0xFF1565C0);
  static const Color pdmaColor = Color(0xFF6A1B9A);
  static const Color pmdColor = Color(0xFF00838F);
}

class AppTheme {
  static ThemeData get lightTheme => ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: AppColors.primary,
          brightness: Brightness.light,
          primary: AppColors.primary,
          secondary: AppColors.accent,
          surface: AppColors.surface,
          error: AppColors.hazardHigh,
        ),
        scaffoldBackgroundColor: AppColors.surface,
        appBarTheme: const AppBarTheme(
          backgroundColor: AppColors.primary,
          foregroundColor: AppColors.textLight,
          elevation: 0,
          centerTitle: true,
          titleTextStyle: TextStyle(
            fontFamily: 'Roboto',
            fontSize: 18,
            fontWeight: FontWeight.w700,
            color: AppColors.textLight,
          ),
        ),
        cardTheme: CardThemeData(
          color: AppColors.cardLight,
          elevation: 2,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
          margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        ),
        elevatedButtonTheme: ElevatedButtonThemeData(
          style: ElevatedButton.styleFrom(
            backgroundColor: AppColors.primary,
            foregroundColor: AppColors.textLight,
            padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 24),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(10),
            ),
            textStyle: const TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
        inputDecorationTheme: InputDecorationTheme(
          filled: true,
          fillColor: Colors.white,
          contentPadding:
              const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(10),
            borderSide: const BorderSide(color: AppColors.primaryLight),
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(10),
            borderSide:
                BorderSide(color: AppColors.primaryLight.withValues(alpha: 0.5)),
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(10),
            borderSide:
                const BorderSide(color: AppColors.primary, width: 2),
          ),
        ),
        chipTheme: ChipThemeData(
          backgroundColor: AppColors.primaryLight.withValues(alpha: 0.2),
          labelStyle: const TextStyle(
            fontSize: 12,
            color: AppColors.primaryDark,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(20),
          ),
        ),
        textTheme: const TextTheme(
          displayLarge: TextStyle(
              fontSize: 32,
              fontWeight: FontWeight.w800,
              color: AppColors.textDark),
          headlineMedium: TextStyle(
              fontSize: 22,
              fontWeight: FontWeight.w700,
              color: AppColors.textDark),
          titleLarge: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w700,
              color: AppColors.textDark),
          bodyLarge: TextStyle(fontSize: 16, color: AppColors.textDark),
          bodyMedium: TextStyle(fontSize: 14, color: AppColors.textDark),
          labelSmall: TextStyle(fontSize: 11, color: AppColors.textMuted),
        ),
      );

  static ThemeData get darkTheme => ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: AppColors.primary,
          brightness: Brightness.dark,
          primary: AppColors.primaryLight,
          secondary: AppColors.accentLight,
          surface: AppColors.surfaceDark,
          error: AppColors.hazardHigh,
        ),
        scaffoldBackgroundColor: AppColors.surfaceDark,
        appBarTheme: const AppBarTheme(
          backgroundColor: Color(0xFF121212),
          foregroundColor: AppColors.textLight,
          elevation: 0,
          centerTitle: true,
        ),
        cardTheme: CardThemeData(
          color: AppColors.cardDark,
          elevation: 2,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
      );
}
