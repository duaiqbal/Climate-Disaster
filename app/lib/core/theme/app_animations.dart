import 'package:flutter/material.dart';

/// Shared animation constants for the auth/onboarding flow and reusable UI.
class AppAnimations {
  AppAnimations._();

  static const Duration splashEntrance = Duration(milliseconds: 1200);
  static const Duration screenEntrance = Duration(milliseconds: 800);
  static const Duration screenEntranceLong = Duration(milliseconds: 900);
  static const Duration pageTransition = Duration(milliseconds: 350);
  static const Duration pageTransitionSlow = Duration(milliseconds: 400);
  static const Duration pageTransitionFade = Duration(milliseconds: 500);
  static const Duration buttonPress = Duration(milliseconds: 120);
  static const Duration buttonStateChange = Duration(milliseconds: 200);
  static const Duration cardStateChange = Duration(milliseconds: 300);
  static const Duration errorBannerResize = Duration(milliseconds: 200);
  static const Duration checkmarkPop = Duration(milliseconds: 250);
  static const Duration loadingBarLoop = Duration(milliseconds: 1200);
  static const Duration splashDisplayHold = Duration(milliseconds: 3500);

  static const Curve entranceCurve = Curves.easeOut;
  static const Curve logoScaleCurve = Curves.easeOutBack;
  static const Curve checkmarkCurve = Curves.easeOutBack;
  static const Curve pressCurve = Curves.easeOut;
  static const Curve stateChangeCurve = Curves.easeOutCubic;

  static const Interval splashLogoFade = Interval(0.0, 0.4, curve: Curves.easeIn);
  static const Interval splashLogoScale = Interval(0.0, 0.55, curve: Curves.easeOutBack);
  static const Interval splashTitle = Interval(0.35, 0.7, curve: Curves.easeOut);
  static const Interval splashSubtitle = Interval(0.5, 0.85, curve: Curves.easeOut);
  static const Interval splashLoader = Interval(0.7, 1.0, curve: Curves.easeOut);
  static const Interval authLogoFade = Interval(0.0, 0.35, curve: Curves.easeOut);
  static const Interval authHeaderFade = Interval(0.15, 0.5, curve: Curves.easeOut);
  static const Interval authCardFade = Interval(0.3, 1.0, curve: Curves.easeOut);
  static const Interval languageHeaderFade = Interval(0.0, 0.4, curve: Curves.easeOut);
  static const Interval languageFooterFade = Interval(0.6, 1.0, curve: Curves.easeOut);

  static Interval languageCardInterval(int index, {double stagger = 0.12, double start = 0.15, double span = 0.45}) {
    final s = (start + (index * stagger)).clamp(0.0, 1.0);
    final e = (s + span).clamp(0.0, 1.0);
    return Interval(s, e, curve: Curves.easeOut);
  }

  static const Offset slideUpSmall = Offset(0, 0.08);
  static const Offset slideUpMedium = Offset(0, 0.12);
  static const Offset slideDownSmall = Offset(0, -0.1);
  static const Offset slideDownMedium = Offset(0, -0.15);
  static const Offset slideFromRight = Offset(0.05, 0);
  static const Offset slideFromLeft = Offset(-0.05, 0);

  static const double pressedScale = 0.97;
  static const double pressedScaleCard = 0.98;
  static const double selectedScaleCard = 1.01;
  static const double logoScaleStart = 0.8;
  static const double checkmarkScaleStart = 0.0;
}