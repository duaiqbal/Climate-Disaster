import 'package:flutter/material.dart';
import '../localization/app_translations.dart';
import '../theme/app_colors.dart';
import '../theme/app_text_styles.dart';
import '../theme/app_animations.dart';

enum AuthTab { login, createAccount }

class AuthTabSwitch extends StatelessWidget {
  final AuthTab activeTab;
  final VoidCallback onLoginTap;
  final VoidCallback onCreateAccountTap;

  const AuthTabSwitch({
    super.key,
    required this.activeTab,
    required this.onLoginTap,
    required this.onCreateAccountTap,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.surfaceVariant,
        borderRadius: BorderRadius.circular(10),
      ),
      padding: const EdgeInsets.all(4),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final tabWidth = (constraints.maxWidth - 8) / 2;
          return Stack(
            children: [
              // Animated sliding pill behind the active tab label
              AnimatedAlign(
                duration: AppAnimations.cardStateChange,
                curve: AppAnimations.stateChangeCurve,
                alignment: activeTab == AuthTab.login
                    ? Alignment.centerLeft
                    : Alignment.centerRight,
                child: Container(
                  width: tabWidth,
                  height: 40,
                  decoration: BoxDecoration(
                    color: AppColors.surface,
                    borderRadius: BorderRadius.circular(8),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withValues(alpha: 0.04),
                        blurRadius: 4,
                        offset: const Offset(0, 1),
                      ),
                    ],
                  ),
                ),
              ),
              Row(
                children: [
                  Expanded(
                    child: InkWell(
                      onTap: onLoginTap,
                      borderRadius: BorderRadius.circular(8),
                      child: Container(
                        padding: const EdgeInsets.symmetric(vertical: 10),
                        alignment: Alignment.center,
                        child: AnimatedDefaultTextStyle(
                          duration: AppAnimations.buttonStateChange,
                          curve: AppAnimations.entranceCurve,
                          style: AppTextStyles.bodyMedium.copyWith(
                            color: activeTab == AuthTab.login
                                ? AppColors.primary
                                : AppColors.textSecondary,
                            fontWeight: FontWeight.w600,
                          ),
                          child: Text(Tr.t('login')),
                        ),
                      ),
                    ),
                  ),
                  Expanded(
                    child: InkWell(
                      onTap: onCreateAccountTap,
                      borderRadius: BorderRadius.circular(8),
                      child: Container(
                        padding: const EdgeInsets.symmetric(vertical: 10),
                        alignment: Alignment.center,
                        child: AnimatedDefaultTextStyle(
                          duration: AppAnimations.buttonStateChange,
                          curve: AppAnimations.entranceCurve,
                          style: AppTextStyles.bodyMedium.copyWith(
                            color: activeTab == AuthTab.createAccount
                                ? AppColors.primary
                                : AppColors.textSecondary,
                            fontWeight: FontWeight.w600,
                          ),
                          child: Text(Tr.t('create_account')),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ],
          );
        },
      ),
    );
  }
}
