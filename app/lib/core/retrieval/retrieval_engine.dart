// LIKE-based retrieval from knowledge.sqlite.
//
// Schema (confirmed against actual bundled knowledge.sqlite — both
// offline_package/ and app/assets/offline_package/ copies):
//
//   CREATE TABLE chunks (
//       chunk_id       TEXT PRIMARY KEY,
//       source_org     TEXT NOT NULL,
//       doc_title      TEXT NOT NULL,
//       pub_date       TEXT,
//       language       TEXT NOT NULL,
//       page_num       INTEGER,
//       chunk_index    INTEGER,
//       chunk_text     TEXT NOT NULL,
//       keywords       TEXT,
//       evidence_level TEXT,
//       char_count     INTEGER,
//       source_url     TEXT          -- nullable; added via ALTER TABLE
//   );
//
// FTS5 is not used — sqflite's bundled SQLite on older Android devices
// may not have the FTS5 extension compiled in, so plain LIKE is safer.
//
// Scoring: one point per query token found in chunk_text (OR over tokens,
// ORDER BY score DESC) — consistent with the backend's _do_search logic.

import '../local_db/local_db.dart';

// ── Data model ──────────────────────────────────────────────────────────────

class RetrievedChunk {
  final String chunkId;
  final String text;          // chunk_text
  final String sourceOrg;     // source_org
  final String sourceTitle;   // doc_title
  final String publicationDate; // pub_date  (may be "unknown")
  final String sourceUrl;     // source_url (may be empty)
  final String evidenceLevel; // evidence_level

  const RetrievedChunk({
    required this.chunkId,
    required this.text,
    required this.sourceOrg,
    required this.sourceTitle,
    required this.publicationDate,
    this.sourceUrl = '',
    this.evidenceLevel = 'official',
  });
}

// ── Roman Urdu normalizer ────────────────────────────────────────────────────

class RomanUrduNormalizer {
  // Maps common Roman Urdu / phonetic spellings to their English equivalents
  // so LIKE search against English chunks finds relevant content.
  // Expanded from the original 8-entry set per Phase 1 requirements.
  static const Map<String, String> _variants = {
    // Flood-related
    'selab':               'flood',
    'sailaab':             'flood',
    'seelab':              'flood',
    'sarab':               'flood',
    'aab o hawaadis':      'flood',
    // Rain-related
    'baarish':             'rain',
    'barish':              'rain',
    'barishat':            'rain',
    'mausam':              'weather',
    'monsoon':             'monsoon',
    // Water
    'paani':               'water',
    'pani':                'water',
    'darya':               'river',
    // Landslide
    'zameen khisakna':     'landslide',
    'zamin khisakna':      'landslide',
    'pathrao':             'landslide',
    'pahaar khiskaao':     'landslide',
    'zameeni khiskaav':    'landslide',
    // Evacuation/safety
    'nikaalna':            'evacuation',
    'bachao':              'safety',
    'hifazat':             'safety',
    'mehfooz':             'safe',
    // Emergency
    'haadsa':              'emergency',
    'aafat':               'disaster',
    'khatar':              'hazard',
    'khatarnaak':          'dangerous',
    'madad':               'help',
    // Preparedness
    'tayyari':             'preparedness',
    'kit':                 'kit',
    'bag':                 'bag',
    // GLOF
    'glacial':             'glacial',
    'baraf':               'glacier',
  };

  static String normalize(String query) {
    String result = query.toLowerCase();
    // Replace longer variants first to avoid partial replacements
    final sorted = _variants.entries.toList()
      ..sort((a, b) => b.key.length.compareTo(a.key.length));
    for (final entry in sorted) {
      result = result.replaceAll(entry.key, entry.value);
    }
    return result;
  }
}

// ── Retrieval engine ─────────────────────────────────────────────────────────

class RetrievalEngine {
  /// Search the local knowledge.sqlite chunks table for [query].
  ///
  /// Matching logic (mirrors backend _do_search):
  ///   - Normalises Roman Urdu tokens
  ///   - Splits on whitespace; each non-empty token becomes a LIKE condition
  ///   - Rows matching ANY token are returned, ordered by number of token hits
  ///   - Also searches the `keywords` column
  ///
  /// Returns at most [limit] results (default 5).
  /// Returns [] on any error (no-throw contract — callers use offline fallback).
  static Future<List<RetrievedChunk>> search(
    String query, {
    int limit = 5,
    String language = 'en',
  }) async {
    try {
      final normalized = RomanUrduNormalizer.normalize(query);
      final db = await LocalDb.knowledgeDb;

      final words = normalized
          .split(RegExp(r'\s+'))
          .where((w) => w.trim().length >= 2)
          .toList();

      if (words.isEmpty) return [];

      // Build LIKE conditions over chunk_text AND keywords
      final likeClauses = words
          .map((_) => '(chunk_text LIKE ? OR keywords LIKE ?)')
          .join(' OR ');

      // Score = count of matching token hits (CASE WHEN ... THEN 1 ELSE 0 END)
      final scoreExpr = words
          .map((_) => 'CASE WHEN chunk_text LIKE ? THEN 1 ELSE 0 END')
          .join(' + ');

      // Parameter lists
      final likeArgs = <Object?>[];
      for (final w in words) {
        likeArgs.add('%$w%'); // for chunk_text LIKE
        likeArgs.add('%$w%'); // for keywords LIKE
      }
      final scoreArgs = words.map((w) => '%$w%').toList();

      final sql = '''
        SELECT
          chunk_id,
          chunk_text,
          source_org,
          doc_title,
          COALESCE(pub_date, 'unknown') AS pub_date,
          COALESCE(source_url, '')      AS source_url,
          COALESCE(evidence_level, 'official') AS evidence_level,
          ($scoreExpr) AS score
        FROM chunks
        WHERE language = ?
          AND ($likeClauses)
        ORDER BY score DESC
        LIMIT ?
      ''';

      final rows = await db.rawQuery(
        sql,
        [...scoreArgs, language, ...likeArgs, limit],
      );

      return rows.map((r) {
        return RetrievedChunk(
          chunkId:         r['chunk_id']       as String,
          text:            r['chunk_text']      as String,
          sourceOrg:       r['source_org']      as String,
          sourceTitle:     r['doc_title']       as String,
          publicationDate: r['pub_date']        as String,
          sourceUrl:       r['source_url']      as String,
          evidenceLevel:   r['evidence_level']  as String,
        );
      }).toList();
    } catch (e) {
      // Swallow all DB errors and return empty — callers use fallback path.
      // In debug mode this will print so issues are visible during development.
      assert(() {
        // ignore: avoid_print
        print('[RetrievalEngine] search error: $e');
        return true;
      }());
      return [];
    }
  }

  /// Convenience: search with language auto-detected from LanguageService.
  /// Falls back to English search if Urdu search returns nothing
  /// (all 315 bundled chunks are English per manifest.json lang_ur=0).
  static Future<List<RetrievedChunk>> searchLocalized(
    String query,
    String langCode, {
    int limit = 5,
  }) async {
    var results = await search(query, limit: limit, language: langCode);
    if (results.isEmpty && langCode != 'en') {
      // Fallback: English chunks carry content for all supported locales
      results = await search(query, limit: limit, language: 'en');
    }
    return results;
  }
}
