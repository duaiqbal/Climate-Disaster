import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/localization/app_localizations.dart';
import '../../core/providers/language_provider.dart';
import '../../core/retrieval/keyword_retriever.dart';
import '../../core/theme/app_theme.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final TextEditingController _queryCtrl = TextEditingController();
  final ScrollController _scrollCtrl = ScrollController();
  final KeywordRetriever _retriever = KeywordRetriever();

  final List<_ChatMessage> _messages = [];
  bool _loading = false;

  // Suggested quick queries per language
  static const Map<String, List<String>> _suggestions = {
    'en': [
      'What should I do during a flood?',
      'How to prepare a go-bag?',
      'Landslide warning signs',
      'Flash flood safety',
      'Evacuation procedure',
    ],
    'ur': [
      'سیلاب کے دوران کیا کریں؟',
      'گو بیگ کیسے تیار کریں؟',
      'لینڈ سلائیڈ کی علامات',
      'فوری نکاسی',
    ],
    'ru': [
      'Flood mein kya karein?',
      'Go-bag kaise banaein?',
      'Landslide ki nishanian',
      'Bachne ka tarika',
    ],
  };

  @override
  void dispose() {
    _queryCtrl.dispose();
    _scrollCtrl.dispose();
    super.dispose();
  }

  Future<void> _ask(String query) async {
    if (query.trim().isEmpty) return;
    final lang = context.read<LanguageProvider>().languageCode;

    setState(() {
      _messages.add(_ChatMessage(text: query, isUser: true));
      _loading = true;
      _queryCtrl.clear();
    });
    _scrollToBottom();

    final results = await _retriever.retrieve(
        query: query, language: lang, topK: 3);

    setState(() {
      _loading = false;
      if (results.isEmpty) {
        _messages.add(_ChatMessage(
          text: AppLocalizations.of(context).noResults,
          isUser: false,
          isError: true,
        ));
      } else {
        for (final r in results) {
          _messages.add(_ChatMessage(
            text: r.chunkText,
            isUser: false,
            sourceOrg: r.sourceOrg,
            docTitle: r.docTitle,
            pubDate: r.pubDate,
            evidenceLevel: r.evidenceLevel,
            sourceBadge: r.sourceBadgeKey,
          ));
        }
      }
    });
    _scrollToBottom();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollCtrl.hasClients) {
        _scrollCtrl.animateTo(
          _scrollCtrl.position.maxScrollExtent,
          duration: const Duration(milliseconds: 350),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);
    final lang = context.watch<LanguageProvider>().languageCode;
    final suggestions = _suggestions[lang] ?? _suggestions['en']!;

    return Scaffold(
      appBar: AppBar(
        title: Text(loc.chat),
        actions: [
          IconButton(
            icon: const Icon(Icons.delete_sweep_outlined),
            tooltip: 'Clear chat',
            onPressed: () => setState(() => _messages.clear()),
          ),
        ],
      ),
      body: Column(
        children: [
          // Quick suggestion chips
          if (_messages.isEmpty)
            Container(
              padding:
                  const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              color: AppColors.surface,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Padding(
                    padding: const EdgeInsets.only(left: 4, bottom: 6),
                    child: Text('Suggested questions',
                        style: Theme.of(context)
                            .textTheme
                            .labelSmall
                            ?.copyWith(color: AppColors.textMuted)),
                  ),
                  Wrap(
                    spacing: 6,
                    runSpacing: 4,
                    children: suggestions
                        .map((s) => ActionChip(
                              label: Text(s,
                                  style: const TextStyle(fontSize: 12)),
                              onPressed: () => _ask(s),
                            ))
                        .toList(),
                  ),
                ],
              ),
            ),

          // Message list
          Expanded(
            child: _messages.isEmpty
                ? Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.chat_bubble_outline_rounded,
                            size: 64,
                            color: AppColors.primaryLight.withValues(alpha: 0.5)),
                        const SizedBox(height: 12),
                        Text(loc.typeQuestion,
                            style: Theme.of(context)
                                .textTheme
                                .bodyMedium
                                ?.copyWith(color: AppColors.textMuted)),
                      ],
                    ),
                  )
                : ListView.builder(
                    controller: _scrollCtrl,
                    padding: const EdgeInsets.symmetric(
                        horizontal: 12, vertical: 12),
                    itemCount: _messages.length + (_loading ? 1 : 0),
                    itemBuilder: (_, i) {
                      if (_loading && i == _messages.length) {
                        return const _TypingIndicator();
                      }
                      return _MessageBubble(msg: _messages[i]);
                    },
                  ),
          ),

          // Input bar
          Container(
            color: Colors.white,
            padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _queryCtrl,
                    minLines: 1,
                    maxLines: 3,
                    decoration: InputDecoration(
                      hintText: loc.typeQuestion,
                      contentPadding: const EdgeInsets.symmetric(
                          horizontal: 16, vertical: 10),
                    ),
                    onSubmitted: _ask,
                    textInputAction: TextInputAction.send,
                  ),
                ),
                const SizedBox(width: 8),
                FloatingActionButton.small(
                  heroTag: 'chat_send',
                  backgroundColor: AppColors.primary,
                  onPressed: () => _ask(_queryCtrl.text),
                  child: const Icon(Icons.send_rounded, color: Colors.white),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ─── Message model ────────────────────────────────────────────────────────────

class _ChatMessage {
  final String text;
  final bool isUser;
  final bool isError;
  final String? sourceOrg;
  final String? docTitle;
  final String? pubDate;
  final String? evidenceLevel;
  final String? sourceBadge;

  const _ChatMessage({
    required this.text,
    required this.isUser,
    this.isError = false,
    this.sourceOrg,
    this.docTitle,
    this.pubDate,
    this.evidenceLevel,
    this.sourceBadge,
  });
}

// ─── Message bubble ───────────────────────────────────────────────────────────

class _MessageBubble extends StatelessWidget {
  final _ChatMessage msg;
  const _MessageBubble({required this.msg});

  Color _badgeColor(String? badge) {
    switch (badge) {
      case 'ndma':
        return AppColors.ndmaColor;
      case 'pdma':
        return AppColors.pdmaColor;
      case 'pmd':
        return AppColors.pmdColor;
      default:
        return AppColors.textMuted;
    }
  }

  @override
  Widget build(BuildContext context) {
    if (msg.isUser) {
      return Align(
        alignment: Alignment.centerRight,
        child: Container(
          margin: const EdgeInsets.only(top: 8, left: 48),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
          decoration: BoxDecoration(
            color: AppColors.primary,
            borderRadius: const BorderRadius.only(
              topLeft: Radius.circular(16),
              topRight: Radius.circular(16),
              bottomLeft: Radius.circular(16),
              bottomRight: Radius.circular(4),
            ),
          ),
          child: Text(msg.text,
              style: const TextStyle(color: Colors.white, fontSize: 14)),
        ),
      );
    }

    // Bot response
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(top: 8, right: 48),
        decoration: BoxDecoration(
          color: msg.isError
              ? AppColors.hazardHigh.withValues(alpha: 0.05)
              : Colors.white,
          borderRadius: const BorderRadius.only(
            topLeft: Radius.circular(4),
            topRight: Radius.circular(16),
            bottomLeft: Radius.circular(16),
            bottomRight: Radius.circular(16),
          ),
          border: Border.all(
            color: msg.isError
                ? AppColors.hazardHigh.withValues(alpha: 0.3)
                : AppColors.primaryLight.withValues(alpha: 0.2),
          ),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.04),
              blurRadius: 4,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(msg.text,
                  style: const TextStyle(
                      fontSize: 14, height: 1.5, color: AppColors.textDark)),
              if (msg.sourceOrg != null) ...[
                const SizedBox(height: 10),
                const Divider(height: 1),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 6,
                  runSpacing: 4,
                  children: [
                    _SourceChip(
                      label: msg.sourceOrg!,
                      color: _badgeColor(msg.sourceBadge),
                    ),
                    if (msg.pubDate != null && msg.pubDate!.isNotEmpty)
                      _SourceChip(
                        label: msg.pubDate!,
                        color: AppColors.textMuted,
                        icon: Icons.calendar_today_outlined,
                      ),
                    if (msg.evidenceLevel != null)
                      _SourceChip(
                        label: msg.evidenceLevel!,
                        color: AppColors.hazardLow,
                        icon: Icons.verified_outlined,
                      ),
                  ],
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _SourceChip extends StatelessWidget {
  final String label;
  final Color color;
  final IconData? icon;

  const _SourceChip({
    required this.label,
    required this.color,
    this.icon,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 10, color: color),
            const SizedBox(width: 3),
          ],
          Text(label,
              style: TextStyle(
                  fontSize: 10,
                  fontWeight: FontWeight.w600,
                  color: color)),
        ],
      ),
    );
  }
}

class _TypingIndicator extends StatelessWidget {
  const _TypingIndicator();

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(top: 8),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
              color: AppColors.primaryLight.withValues(alpha: 0.2)),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SizedBox(
              height: 16,
              width: 16,
              child: CircularProgressIndicator(
                  strokeWidth: 2, color: AppColors.primary),
            ),
            const SizedBox(width: 8),
            Text(AppLocalizations.of(context).loading,
                style: const TextStyle(
                    color: AppColors.textMuted, fontSize: 13)),
          ],
        ),
      ),
    );
  }
}
