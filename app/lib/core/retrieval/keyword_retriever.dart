import '../local_db/database_helper.dart';
import 'roman_urdu_normalizer.dart';

/// A retrieval result wrapping a single knowledge chunk.
class RetrievalResult {
  final String chunkId;
  final String sourceOrg;
  final String docTitle;
  final String pubDate;
  final String chunkText;
  final String language;
  final String evidenceLevel;
  final int score;

  const RetrievalResult({
    required this.chunkId,
    required this.sourceOrg,
    required this.docTitle,
    required this.pubDate,
    required this.chunkText,
    required this.language,
    required this.evidenceLevel,
    required this.score,
  });

  factory RetrievalResult.fromRow(Map<String, dynamic> row) {
    return RetrievalResult(
      chunkId: row['chunk_id']?.toString() ?? '',
      sourceOrg: row['source_org']?.toString() ?? '',
      docTitle: row['doc_title']?.toString() ?? '',
      pubDate: row['pub_date']?.toString() ?? '',
      chunkText: row['chunk_text']?.toString() ?? '',
      language: row['language']?.toString() ?? 'en',
      evidenceLevel: row['evidence_level']?.toString() ?? 'official',
      score: (row['score'] as num?)?.toInt() ?? 0,
    );
  }

  /// Returns a badge color string based on source org.
  String get sourceBadgeKey {
    final org = sourceOrg.toUpperCase();
    if (org.contains('NDMA')) return 'ndma';
    if (org.contains('PDMA')) return 'pdma';
    if (org.contains('PMD')) return 'pmd';
    return 'other';
  }
}

/// Offline keyword retriever — uses SQLite LIKE matching.
/// For Roman Urdu queries, expands variant spellings before searching.
class KeywordRetriever {
  final DatabaseHelper _db;

  KeywordRetriever({DatabaseHelper? db})
      : _db = db ?? DatabaseHelper.instance;

  Future<List<RetrievalResult>> retrieve({
    required String query,
    required String language,
    int topK = 5,
  }) async {
    if (query.trim().isEmpty) return [];

    // Determine if we should treat this as Roman Urdu —
    // either explicitly requested OR auto-detected from query content.
    final bool isRomanUrdu =
        language == 'ru' || RomanUrduNormalizer.isLikelyRomanUrdu(query);

    // Expand query to cover spelling variants when Roman Urdu is detected.
    final String effectiveQuery = isRomanUrdu
        ? RomanUrduNormalizer.expandQuery(query).join(' ')
        : query;

    final String effectiveLang = isRomanUrdu ? 'ru' : language;

    final rows = await _db.searchChunks(
      query: effectiveQuery,
      language: effectiveLang,
      limit: topK,
    );

    // If Roman Urdu returns no results, fall back to English
    if (rows.isEmpty && effectiveLang == 'ru') {
      final fallback = await _db.searchChunks(
        query: query,
        language: 'en',
        limit: topK,
      );
      return fallback.map((r) => RetrievalResult.fromRow(r)).toList();
    }

    return rows.map((r) => RetrievalResult.fromRow(r)).toList();
  }

  /// Convenience — returns plain text of top results joined for display.
  Future<String> retrieveText({
    required String query,
    required String language,
    int topK = 3,
  }) async {
    final results = await retrieve(query: query, language: language, topK: topK);
    if (results.isEmpty) return '';
    return results.map((r) => r.chunkText).join('\n\n');
  }
}
