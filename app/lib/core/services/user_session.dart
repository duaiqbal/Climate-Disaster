import 'package:flutter/foundation.dart';

/// In-memory source of truth for the authenticated user during this app run.
class UserSession extends ChangeNotifier {
  UserSession._();

  static final UserSession instance = UserSession._();

  int? userId;
  String? name;
  String? email;
  String? authToken;
  String? refreshToken;

  bool get isLoggedIn => authToken != null && authToken!.isNotEmpty;

  void setFromLoginResponse(Map<String, dynamic> response) {
    final user = response['user'];
    if (user is! Map) {
      throw const FormatException('The server returned no user profile.');
    }

    userId = int.tryParse(user['id'].toString());
    name = user['name']?.toString();
    email = user['email']?.toString();
    authToken = response['access_token']?.toString();
    refreshToken = response['refresh_token']?.toString();
    if (!isLoggedIn) {
      throw const FormatException('The server returned no access token.');
    }
    notifyListeners();
  }

  void clear() {
    userId = null;
    name = null;
    email = null;
    authToken = null;
    refreshToken = null;
    notifyListeners();
  }
}
