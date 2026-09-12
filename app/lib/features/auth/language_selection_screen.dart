import 'package:flutter/material.dart';
import '../../core/localization/language_service.dart';
import '../../core/localization/app_translations.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_text_styles.dart';
import '../../core/services/user_session.dart';
import 'login_screen.dart';
import '../navigation/main_navigation_shell.dart';

class LanguageSelectionScreen extends StatefulWidget {
  const LanguageSelectionScreen({super.key});

  @override
  State<LanguageSelectionScreen> createState() => _LanguageSelectionScreenState();
}

class _LanguageSelectionScreenState extends State<LanguageSelectionScreen>
    with SingleTickerProviderStateMixin {
  late AppLanguage _selected;
  late AnimationController _entranceController;
  late Animation<double> _headerFade;
  late Animation<Offset> _headerSlide;
  late List<Animation<double>> _cardFades;
  late List<Animation<Offset>> _cardSlides;
  late Animation<double> _footerFade;

  @override
  void initState() {
    super.initState();
    _selected = LanguageService.instance.current;

    _entranceController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    );

    _headerFade = CurvedAnimation(
      parent: _entranceController,
      curve: const Interval(0.0, 0.4, curve: Curves.easeOut),
    );
    _headerSlide = Tween<Offset>(
      begin: const Offset(0, -0.15),
      end: Offset.zero,
    ).animate(_headerFade);

    _cardFades = List.generate(3, (i) {
      final start = 0.15 + (i * 0.12);
      final end = (start + 0.45).clamp(0.0, 1.0);
      return CurvedAnimation(
        parent: _entranceController,
        curve: Interval(start, end, curve: Curves.easeOut),
      );
    });

    _cardSlides = _cardFades.map((fade) {
      return Tween<Offset>(
        begin: const Offset(0, 0.12),
        end: Offset.zero,
      ).animate(fade);
    }).toList();

    _footerFade = CurvedAnimation(
      parent: _entranceController,
      curve: const Interval(0.6, 1.0, curve: Curves.easeOut),
    );

    _entranceController.forward();
  }

  @override
  void dispose() {
    _entranceController.dispose();
    super.dispose();
  }

  void _selectLanguage(AppLanguage lang) {
    setState(() => _selected = lang);
    LanguageService.instance.setLanguage(lang);
  }

  void _continue() {
    LanguageService.instance.setLanguage(_selected);
    if (Navigator.of(context).canPop()) {
      Navigator.of(context).pop();
      return;
    }
    final destination = UserSession.instance.isLoggedIn
        ? const MainNavigationShell()
        : const LoginScreen();
    Navigator.of(context).pushReplacement(
      PageRouteBuilder(
        transitionDuration: const Duration(milliseconds: 400),
        pageBuilder: (_, animation, __) => destination,
        transitionsBuilder: (_, animation, __, child) {
          return FadeTransition(
            opacity: animation,
            child: SlideTransition(
              position: Tween<Offset>(
                begin: const Offset(0, 0.03),
                end: Offset.zero,
              ).animate(CurvedAnimation(parent: animation, curve: Curves.easeOut)),
              child: child,
            ),
          );
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final size = MediaQuery.sizeOf(context);
    final isWide = size.width > 600;
    final horizontalPadding = isWide ? size.width * 0.12 : 20.0;

    return Scaffold(
      backgroundColor: AppColors.background,
      body: DecoratedBox(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [
              AppColors.primary.withValues(alpha: 0.06),
              AppColors.background,
              AppColors.background,
            ],
            stops: const [0.0, 0.35, 1.0],
          ),
        ),
        child: SafeArea(
          child: LayoutBuilder(
            builder: (context, constraints) {
              return SingleChildScrollView(
                padding: EdgeInsets.symmetric(
                  horizontal: horizontalPadding,
                  vertical: 16,
                ),
                child: ConstrainedBox(
                  constraints: BoxConstraints(
                    minHeight: constraints.maxHeight - 32,
                    maxWidth: isWide ? 560 : double.infinity,
                  ),
                  child: Center(
                    child: IntrinsicHeight(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          if (Navigator.of(context).canPop())
                            Align(
                              alignment: Alignment.centerLeft,
                              child: Material(
                                color: Colors.transparent,
                                child: InkWell(
                                  borderRadius: BorderRadius.circular(24),
                                  onTap: () => Navigator.of(context).maybePop(),
                                  child: Padding(
                                    padding: const EdgeInsets.all(8),
                                    child: Container(
                                      padding: const EdgeInsets.all(6),
                                      decoration: BoxDecoration(
                                        color: AppColors.surface,
                                        shape: BoxShape.circle,
                                        border: Border.all(color: AppColors.border),
                                      ),
                                      child: const Icon(Icons.arrow_back,
                                          color: AppColors.textPrimary, size: 20),
                                    ),
                                  ),
                                ),
                              ),
                            ),
                          const SizedBox(height: 8),

                          // Header
                          FadeTransition(
                            opacity: _headerFade,
                            child: SlideTransition(
                              position: _headerSlide,
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  ShaderMask(
                                    shaderCallback: (bounds) => LinearGradient(
                                      colors: [
                                        AppColors.primary,
                                        AppColors.primary.withValues(alpha: 0.65),
                                      ],
                                    ).createShader(bounds),
                                    child: Text(
                                      Tr.t('choose_language'),
                                      style: AppTextStyles.screenHeader.copyWith(
                                        color: Colors.white,
                                        fontWeight: FontWeight.w800,
                                      ),
                                    ),
                                  ),
                                  const SizedBox(height: 10),
                                  Text(
                                    Tr.t('select_language_subtitle'),
                                    style: AppTextStyles.body.copyWith(
                                      color: AppColors.textSecondary,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                          const SizedBox(height: 32),

                          // Cards
                          FadeTransition(
                            opacity: _cardFades[0],
                            child: SlideTransition(
                              position: _cardSlides[0],
                              child: _LanguageCard(
                                title: 'English',
                                subtitle: 'English guidance and interface',
                                selected: _selected == AppLanguage.english,
                                onTap: () => _selectLanguage(AppLanguage.english),
                              ),
                            ),
                          ),
                          const SizedBox(height: 14),
                          FadeTransition(
                            opacity: _cardFades[1],
                            child: SlideTransition(
                              position: _cardSlides[1],
                              child: _LanguageCard(
                                title: 'اردو',
                                titleAlignment: TextAlign.right,
                                subtitle: 'اردو میں رہنمائی اور معلومات',
                                subtitleAlignment: TextAlign.right,
                                selected: _selected == AppLanguage.urdu,
                                onTap: () => _selectLanguage(AppLanguage.urdu),
                              ),
                            ),
                          ),
                          const SizedBox(height: 14),
                          FadeTransition(
                            opacity: _cardFades[2],
                            child: SlideTransition(
                              position: _cardSlides[2],
                              child: _LanguageCard(
                                title: 'Roman Urdu',
                                subtitle: 'Roman Urdu mein rehnumai aur maloomat',
                                selected: _selected == AppLanguage.romanUrdu,
                                onTap: () => _selectLanguage(AppLanguage.romanUrdu),
                              ),
                            ),
                          ),
                          const SizedBox(height: 16),
                          const Spacer(),

                          FadeTransition(
                            opacity: _footerFade,
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.stretch,
                              children: [
                                Container(
                                  height: 1,
                                  decoration: BoxDecoration(
                                    gradient: LinearGradient(
                                      colors: [
                                        Colors.transparent,
                                        AppColors.border,
                                        Colors.transparent,
                                      ],
                                    ),
                                  ),
                                ),
                                const SizedBox(height: 16),
                                _AnimatedContinueButton(onPressed: _continue),
                                const SizedBox(height: 10),
                                Center(
                                  child: Text(
                                    Tr.t('language_can_change_later'),
                                    style: AppTextStyles.caption.copyWith(
                                      color: AppColors.textMuted,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              );
            },
          ),
        ),
      ),
    );
  }
}

class _AnimatedContinueButton extends StatefulWidget {
  final VoidCallback onPressed;
  const _AnimatedContinueButton({required this.onPressed});

  @override
  State<_AnimatedContinueButton> createState() => _AnimatedContinueButtonState();
}

class _AnimatedContinueButtonState extends State<_AnimatedContinueButton> {
  bool _pressed = false;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTapDown: (_) => setState(() => _pressed = true),
      onTapUp: (_) => setState(() => _pressed = false),
      onTapCancel: () => setState(() => _pressed = false),
      onTap: widget.onPressed,
      child: AnimatedScale(
        scale: _pressed ? 0.97 : 1.0,
        duration: const Duration(milliseconds: 120),
        curve: Curves.easeOut,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          width: double.infinity,
          padding: const EdgeInsets.symmetric(vertical: 16),
          decoration: BoxDecoration(
            gradient: LinearGradient(
              colors: [
                AppColors.primary,
                AppColors.primary.withValues(alpha: 0.85),
              ],
              begin: Alignment.centerLeft,
              end: Alignment.centerRight,
            ),
            borderRadius: BorderRadius.circular(14),
            boxShadow: [
              BoxShadow(
                color: AppColors.primary.withValues(alpha: _pressed ? 0.15 : 0.30),
                blurRadius: _pressed ? 8 : 16,
                offset: Offset(0, _pressed ? 2 : 6),
              ),
            ],
          ),
          child: Center(
            child: Text(
              Tr.t('continue'),
              style: AppTextStyles.button.copyWith(color: Colors.white),
            ),
          ),
        ),
      ),
    );
  }
}

class _LanguageCard extends StatefulWidget {
  final String title;
  final String subtitle;
  final TextAlign titleAlignment;
  final TextAlign subtitleAlignment;
  final bool selected;
  final VoidCallback onTap;

  const _LanguageCard({
    required this.title,
    required this.subtitle,
    required this.selected,
    required this.onTap,
    this.titleAlignment = TextAlign.left,
    this.subtitleAlignment = TextAlign.left,
  });

  @override
  State<_LanguageCard> createState() => _LanguageCardState();
}

class _LanguageCardState extends State<_LanguageCard> {
  bool _pressed = false;

  @override
  Widget build(BuildContext context) {
    final selected = widget.selected;
    return GestureDetector(
      onTapDown: (_) => setState(() => _pressed = true),
      onTapUp: (_) => setState(() => _pressed = false),
      onTapCancel: () => setState(() => _pressed = false),
      onTap: widget.onTap,
      child: AnimatedScale(
        scale: _pressed ? 0.98 : (selected ? 1.01 : 1.0),
        duration: const Duration(milliseconds: 150),
        curve: Curves.easeOut,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOutCubic,
          padding: const EdgeInsets.all(18),
          decoration: BoxDecoration(
            gradient: selected
                ? LinearGradient(
                    colors: [
                      AppColors.primaryContainer,
                      AppColors.primaryContainer.withValues(alpha: 0.7),
                    ],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  )
                : null,
            color: selected ? null : AppColors.surface,
            borderRadius: BorderRadius.circular(18),
            border: Border.all(
              color: selected ? AppColors.primary : AppColors.border,
              width: selected ? 1.8 : 1,
            ),
            boxShadow: selected
                ? [
                    BoxShadow(
                      color: AppColors.primary.withValues(alpha: 0.18),
                      blurRadius: 16,
                      offset: const Offset(0, 4),
                    ),
                  ]
                : [
                    BoxShadow(
                      color: Colors.black.withValues(alpha: 0.03),
                      blurRadius: 6,
                      offset: const Offset(0, 2),
                    ),
                  ],
          ),
          child: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: widget.titleAlignment == TextAlign.right
                      ? CrossAxisAlignment.end
                      : CrossAxisAlignment.start,
                  children: [
                    Text(
                      widget.title,
                      textAlign: widget.titleAlignment,
                      style: AppTextStyles.cardTitle.copyWith(
                        fontSize: 17,
                        fontWeight: selected ? FontWeight.w700 : FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      widget.subtitle,
                      textAlign: widget.subtitleAlignment,
                      style: AppTextStyles.body.copyWith(
                        color: AppColors.textSecondary,
                        fontSize: 13,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 12),
              SizedBox(
                width: 24,
                height: 24,
                child: Stack(
                  alignment: Alignment.center,
                  children: [
                    AnimatedOpacity(
                      opacity: selected ? 0.0 : 1.0,
                      duration: const Duration(milliseconds: 200),
                      child: Container(
                        width: 24,
                        height: 24,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          border: Border.all(color: AppColors.border, width: 1.4),
                        ),
                      ),
                    ),
                    AnimatedScale(
                      scale: selected ? 1.0 : 0.0,
                      duration: const Duration(milliseconds: 250),
                      curve: Curves.easeOutBack,
                      child: Container(
                        width: 24,
                        height: 24,
                        decoration: BoxDecoration(
                          gradient: LinearGradient(
                            colors: [
                              AppColors.primary,
                              AppColors.primary.withValues(alpha: 0.8),
                            ],
                          ),
                          shape: BoxShape.circle,
                          boxShadow: [
                            BoxShadow(
                              color: AppColors.primary.withValues(alpha: 0.4),
                              blurRadius: 6,
                            ),
                          ],
                        ),
                        child: const Icon(Icons.check, color: Colors.white, size: 15),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}