import 'package:flutter/material.dart';
import '../../core/localization/app_translations.dart';
import '../../core/services/api_service.dart';
import '../../core/services/user_session.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_text_styles.dart';
import '../../core/widgets/auth_tab_switch.dart';
import '../navigation/main_navigation_shell.dart';
import 'login_screen.dart';

class SignupScreen extends StatefulWidget {
  const SignupScreen({super.key});

  @override
  State<SignupScreen> createState() => _SignupScreenState();
}

class _SignupScreenState extends State<SignupScreen> {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  final _confirmPasswordController = TextEditingController();
  bool _isLoading = false;
  bool _obscurePassword = true;
  bool _obscureConfirmPassword = true;
  String? _errorMessage;

  @override
  void dispose() {
    _nameController.dispose();
    _emailController.dispose();
    _passwordController.dispose();
    _confirmPasswordController.dispose();
    super.dispose();
  }

  Future<void> _handleCreateAccount() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });
    try {
      final registration = await ApiService.postDetailed('/auth/register', {
        'name': _nameController.text.trim(),
        'email': _emailController.text.trim(),
        'password': _passwordController.text,
        'language': 'en',
      });
      if (registration.statusCode != 201 || registration.body is! Map) {
        throw ApiException(_apiError(registration.body, 'Registration failed.'),
            registration.statusCode);
      }

      // Registration returns the profile only; login obtains the access token.
      final login = await ApiService.postDetailed('/auth/login', {
        'email': _emailController.text.trim(),
        'password': _passwordController.text,
      });
      if (login.statusCode != 200 || login.body is! Map) {
        throw ApiException(
            _apiError(login.body, 'Account created, but login failed.'),
            login.statusCode);
      }
      UserSession.instance.setFromLoginResponse(
        Map<String, dynamic>.from(login.body as Map),
      );
      if (!mounted) return;
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => const MainNavigationShell()),
      );
    } catch (error) {
      if (mounted) setState(() => _errorMessage = error.toString());
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  String _apiError(dynamic body, String fallback) {
    if (body is Map && body['detail'] is String)
      return body['detail'] as String;
    if (body is Map && body['detail'] is List) {
      return (body['detail'] as List).map((item) {
        if (item is Map && item['msg'] != null) return item['msg'].toString();
        return item.toString();
      }).join(', ');
    }
    return fallback;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 24),
          child: Column(
            children: [
              const SizedBox(height: 16),
              Container(
                width: 64,
                height: 64,
                decoration: BoxDecoration(
                  color: AppColors.surface,
                  borderRadius: BorderRadius.circular(16),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withValues(alpha: 0.05),
                      blurRadius: 6,
                      offset: const Offset(0, 2),
                    ),
                  ],
                ),
                child: const Icon(Icons.shield_outlined,
                    color: AppColors.primary, size: 32),
              ),
              const SizedBox(height: 16),
              Text(
                Tr.t('app_title'),
                textAlign: TextAlign.center,
                style: AppTextStyles.screenHeader,
              ),
              const SizedBox(height: 6),
              Text(
                Tr.t('app_subtitle'),
                textAlign: TextAlign.center,
                style:
                    AppTextStyles.body.copyWith(color: AppColors.textSecondary),
              ),
              const SizedBox(height: 24),
              Container(
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  color: AppColors.surface,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: AppColors.border),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withValues(alpha: 0.05),
                      blurRadius: 8,
                      offset: const Offset(0, 2),
                    ),
                  ],
                ),
                child: Form(
                  key: _formKey,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      AuthTabSwitch(
                        activeTab: AuthTab.createAccount,
                        onLoginTap: () {
                          Navigator.of(context).pushReplacement(
                            MaterialPageRoute(
                                builder: (_) => const LoginScreen()),
                          );
                        },
                        onCreateAccountTap: () {},
                      ),
                      const SizedBox(height: 20),
                      if (_errorMessage != null) ...[
                        Text(_errorMessage!,
                            style: const TextStyle(color: Colors.red)),
                        const SizedBox(height: 12),
                      ],
                      Text(Tr.t('name'),
                          style: AppTextStyles.bodyMedium
                              .copyWith(fontWeight: FontWeight.w600)),
                      const SizedBox(height: 6),
                      TextFormField(
                        controller: _nameController,
                        style: AppTextStyles.body
                            .copyWith(color: AppColors.textPrimary),
                        decoration: InputDecoration(
                          hintText: Tr.t('name_hint'),
                          hintStyle: AppTextStyles.body
                              .copyWith(color: AppColors.textDisabled),
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(10),
                            borderSide:
                                const BorderSide(color: AppColors.border),
                          ),
                          enabledBorder: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(10),
                            borderSide:
                                const BorderSide(color: AppColors.border),
                          ),
                          focusedBorder: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(10),
                            borderSide: const BorderSide(
                                color: AppColors.primary, width: 1.5),
                          ),
                        ),
                        validator: (v) {
                          if (v == null || v.trim().isEmpty) {
                            return Tr.t('validation_name_required');
                          }
                          return null;
                        },
                      ),
                      const SizedBox(height: 16),
                      Text(Tr.t('email'),
                          style: AppTextStyles.bodyMedium
                              .copyWith(fontWeight: FontWeight.w600)),
                      const SizedBox(height: 6),
                      TextFormField(
                        controller: _emailController,
                        keyboardType: TextInputType.emailAddress,
                        style: AppTextStyles.body
                            .copyWith(color: AppColors.textPrimary),
                        decoration: InputDecoration(
                          hintText: Tr.t('email_hint'),
                          hintStyle: AppTextStyles.body
                              .copyWith(color: AppColors.textDisabled),
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(10),
                            borderSide:
                                const BorderSide(color: AppColors.border),
                          ),
                          enabledBorder: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(10),
                            borderSide:
                                const BorderSide(color: AppColors.border),
                          ),
                          focusedBorder: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(10),
                            borderSide: const BorderSide(
                                color: AppColors.primary, width: 1.5),
                          ),
                        ),
                        validator: (v) {
                          if (v == null || v.trim().isEmpty) {
                            return Tr.t('validation_email_required');
                          }
                          if (!RegExp(r'^[\w\-.]+@[\w\-]+\.\w+$')
                              .hasMatch(v.trim())) {
                            return Tr.t('validation_email_invalid');
                          }
                          return null;
                        },
                      ),
                      const SizedBox(height: 16),
                      Text(Tr.t('password'),
                          style: AppTextStyles.bodyMedium
                              .copyWith(fontWeight: FontWeight.w600)),
                      const SizedBox(height: 6),
                      TextFormField(
                        controller: _passwordController,
                        obscureText: _obscurePassword,
                        style: AppTextStyles.body
                            .copyWith(color: AppColors.textPrimary),
                        decoration: InputDecoration(
                          hintText: '••••••••',
                          hintStyle: AppTextStyles.body
                              .copyWith(color: AppColors.textDisabled),
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(10),
                            borderSide:
                                const BorderSide(color: AppColors.border),
                          ),
                          enabledBorder: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(10),
                            borderSide:
                                const BorderSide(color: AppColors.border),
                          ),
                          focusedBorder: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(10),
                            borderSide: const BorderSide(
                                color: AppColors.primary, width: 1.5),
                          ),
                          suffixIcon: IconButton(
                            icon: Icon(
                              _obscurePassword
                                  ? Icons.visibility_outlined
                                  : Icons.visibility_off_outlined,
                              color: AppColors.textMuted,
                              size: 20,
                            ),
                            onPressed: () => setState(
                                () => _obscurePassword = !_obscurePassword),
                          ),
                        ),
                        validator: (v) {
                          if (v == null || v.isEmpty) {
                            return Tr.t('validation_password_required');
                          }
                          if (v.length < 8) {
                            return Tr.t('validation_password_short');
                          }
                          return null;
                        },
                      ),
                      const SizedBox(height: 16),
                      Text(Tr.t('confirm_password'),
                          style: AppTextStyles.bodyMedium
                              .copyWith(fontWeight: FontWeight.w600)),
                      const SizedBox(height: 6),
                      TextFormField(
                        controller: _confirmPasswordController,
                        obscureText: _obscureConfirmPassword,
                        style: AppTextStyles.body
                            .copyWith(color: AppColors.textPrimary),
                        decoration: InputDecoration(
                          hintText: '••••••••',
                          hintStyle: AppTextStyles.body
                              .copyWith(color: AppColors.textDisabled),
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(10),
                            borderSide:
                                const BorderSide(color: AppColors.border),
                          ),
                          enabledBorder: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(10),
                            borderSide:
                                const BorderSide(color: AppColors.border),
                          ),
                          focusedBorder: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(10),
                            borderSide: const BorderSide(
                                color: AppColors.primary, width: 1.5),
                          ),
                          suffixIcon: IconButton(
                            icon: Icon(
                              _obscureConfirmPassword
                                  ? Icons.visibility_outlined
                                  : Icons.visibility_off_outlined,
                              color: AppColors.textMuted,
                              size: 20,
                            ),
                            onPressed: () => setState(() =>
                                _obscureConfirmPassword =
                                    !_obscureConfirmPassword),
                          ),
                        ),
                        validator: (v) {
                          if (v == null || v.isEmpty) {
                            return Tr.t('validation_confirm_required');
                          }
                          if (v != _passwordController.text) {
                            return Tr.t('validation_passwords_mismatch');
                          }
                          return null;
                        },
                      ),
                      const SizedBox(height: 20),
                      SizedBox(
                        width: double.infinity,
                        child: ElevatedButton(
                          onPressed: _isLoading ? null : _handleCreateAccount,
                          style: ElevatedButton.styleFrom(
                            backgroundColor: AppColors.primary,
                            foregroundColor: Colors.white,
                            padding: const EdgeInsets.symmetric(vertical: 14),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(10),
                            ),
                          ),
                          child: _isLoading
                              ? const SizedBox(
                                  height: 20,
                                  width: 20,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                    color: Colors.white,
                                  ),
                                )
                              : Text(
                                  Tr.t('sign_up_btn'),
                                  style: AppTextStyles.button,
                                ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
