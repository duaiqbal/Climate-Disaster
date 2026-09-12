import 'package:flutter/material.dart';
import '../core/theme/app_colors.dart';

/// Shared visual entrance treatment for feature screens.
class ScreenEntrance extends StatefulWidget {
  final Widget child;
  final double maxWidth;

  const ScreenEntrance({
    super.key,
    required this.child,
    this.maxWidth = 1100,
  });

  @override
  State<ScreenEntrance> createState() => _ScreenEntranceState();
}

class _ScreenEntranceState extends State<ScreenEntrance>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late final Animation<double> _fade;
  late final Animation<Offset> _slide;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 800),
    );
    _fade = CurvedAnimation(
      parent: _controller,
      curve: const Interval(0.0, 0.8, curve: Curves.easeOut),
    );
    _slide = Tween<Offset>(
      begin: const Offset(0, 0.04),
      end: Offset.zero,
    ).animate(CurvedAnimation(
      parent: _controller,
      curve: const Interval(0.1, 1.0, curve: Curves.easeOutCubic),
    ));
    _controller.forward();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final content = ConstrainedBox(
          constraints: BoxConstraints(maxWidth: widget.maxWidth),
          child: widget.child,
        );
        return DecoratedBox(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [
                AppColors.primary.withValues(alpha: 0.035),
                Colors.transparent,
              ],
            ),
          ),
          child: Center(
            child: FadeTransition(
              opacity: _fade,
              child: SlideTransition(position: _slide, child: content),
            ),
          ),
        );
      },
    );
  }
}
