import 'dart:io';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/services.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:sqflite/sqflite.dart';

import '../config/app_config.dart';

/// Manages both offline SQLite databases:
///   knowledge.sqlite    — verified official content (chunks + metadata + alerts)
///   hazard_grid.sqlite  — precomputed GIS hazard cells
///
/// Version strategy:
///   A version number is stored in SharedPreferences ('knowledge_db_version').
///   On every app launch, if the stored version differs from
///   [AppConfig.bundledDbVersion], the bundled asset is re-copied and the
///   local file is replaced.  This ensures users always get the latest
///   offline package after an app upgrade.
class DatabaseHelper {
  DatabaseHelper._();
  static final DatabaseHelper instance = DatabaseHelper._();

  Database? _knowledgeDb;
  Database? _hazardDb;

  // ── Init ──────────────────────────────────────────────────────────────────

  Future<void> init() async {
    if (kIsWeb) return; // sqflite not supported on web
    _knowledgeDb = await _openDb('knowledge.sqlite', versionKey: 'knowledge_db_version');
    _hazardDb    = await _openDb('hazard_grid.sqlite', versionKey: 'hazard_db_version');
    await _ensureAlertsTable(_knowledgeDb!);
  }

  Future<Database> _openDb(String filename, {required String versionKey}) async {
    final dir    = await getApplicationDocumentsDirectory();
    final dbPath = p.join(dir.path, filename);

    final prefs         = await SharedPreferences.getInstance();
    final storedVersion = prefs.getInt(versionKey) ?? 0;
    final needsCopy     = !await File(dbPath).exists() ||
                          storedVersion < AppConfig.bundledDbVersion;

    if (needsCopy) {
      await _copyAssetDb(filename, dbPath);
      await prefs.setInt(versionKey, AppConfig.bundledDbVersion);
    }

    return await openDatabase(dbPath, readOnly: false);
  }

  Future<void> _copyAssetDb(String filename, String destPath) async {
    final data  = await rootBundle.load('assets/offline_package/$filename');
    final bytes = data.buffer.asUint8List();
    await File(destPath).writeAsBytes(bytes, flush: true);
  }

  /// Ensures the alerts table exists in knowledge.sqlite.
  /// The pipeline may or may not have created it; we guarantee it here
  /// so getAlerts() / upsertAlert() never throw "no such table".
  Future<void> _ensureAlertsTable(Database db) async {
    await db.execute('''
      CREATE TABLE IF NOT EXISTS alerts (
        alert_id    TEXT PRIMARY KEY,
        title       TEXT NOT NULL,
        body        TEXT NOT NULL,
        hazard_type TEXT,
        severity    TEXT,
        issued_at   TEXT,
        source_org  TEXT,
        district    TEXT
      )
    ''');

    // Also ensure package_meta exists so profile screen never crashes.
    await db.execute('''
      CREATE TABLE IF NOT EXISTS package_meta (
        key   TEXT PRIMARY KEY,
        value TEXT
      )
    ''');
  }

  // ── Knowledge queries ─────────────────────────────────────────────────────

  /// Keyword search over chunks — language-aware LIKE matching.
  /// Returns up to [limit] results ordered by relevance score (hit count).
  Future<List<Map<String, dynamic>>> searchChunks({
    required String query,
    required String language,
    int limit = 10,
  }) async {
    if (kIsWeb || _knowledgeDb == null) return [];
    final db = _knowledgeDb!;
    final tokens = _tokenize(query, language);
    if (tokens.isEmpty) return [];

    // WHERE clause: at least one token must match chunk_text or keywords
    final whereParts = tokens
        .map((_) => '(chunk_text LIKE ? OR keywords LIKE ?)')
        .join(' OR ');
    final whereArgs = tokens.expand((t) => ['%$t%', '%$t%']).toList();

    // Score expression: count of matching tokens in chunk_text
    final scoreExpr = tokens
        .map((_) => 'CASE WHEN chunk_text LIKE ? THEN 1 ELSE 0 END')
        .join(' + ');
    final scoreArgs = tokens.map((t) => '%$t%').toList();

    final rows = await db.rawQuery(
      '''
      SELECT chunk_id, source_org, doc_title, pub_date, chunk_text,
             keywords, language, evidence_level,
             ($scoreExpr) AS score
      FROM chunks
      WHERE language = ? AND ($whereParts)
      ORDER BY score DESC
      LIMIT ?
      ''',
      [...scoreArgs, language, ...whereArgs, limit],
    );
    return rows;
  }

  /// Returns all chunks without filtering (for browse / debug).
  Future<List<Map<String, dynamic>>> getAllChunks({
    String language = 'en',
    int limit = 50,
  }) async {
    if (kIsWeb || _knowledgeDb == null) return [];
    return _knowledgeDb!.query(
      'chunks',
      where: 'language = ?',
      whereArgs: [language],
      orderBy: 'source_org, doc_title',
      limit: limit,
    );
  }

  /// Returns all available alerts from the local cache.
  Future<List<Map<String, dynamic>>> getAlerts() async {
    if (kIsWeb || _knowledgeDb == null) return [];
    try {
      return await _knowledgeDb!.query(
        'alerts',
        orderBy: 'issued_at DESC',
        limit: 50,
      );
    } catch (_) {
      return [];
    }
  }

  /// Inserts or replaces a synced alert.
  Future<void> upsertAlert(Map<String, dynamic> alert) async {
    if (kIsWeb || _knowledgeDb == null) return;
    try {
      await _knowledgeDb!.insert(
        'alerts',
        alert,
        conflictAlgorithm: ConflictAlgorithm.replace,
      );
    } catch (_) {
      // Table may not exist in very old builds; silently skip.
    }
  }

  // ── Hazard grid queries ───────────────────────────────────────────────────

  /// Looks up the hazard cell nearest to [lat], [lon].
  /// Returns null if the coordinate is outside the study area.
  Future<Map<String, dynamic>?> getHazardCell(double lat, double lon) async {
    if (kIsWeb || _hazardDb == null) return null;
    final db   = _hazardDb!;
    final rows = await db.rawQuery(
      '''
      SELECT cell_id, lat, lon, hazard_level, slope_deg, river_dist_km,
             elevation_m, contributing_factors
      FROM hazard_grid
      WHERE lat BETWEEN ? AND ?
        AND lon BETWEEN ? AND ?
      ORDER BY ABS(lat - ?) + ABS(lon - ?) ASC
      LIMIT 1
      ''',
      [lat - 0.01, lat + 0.01, lon - 0.01, lon + 0.01, lat, lon],
    );
    return rows.isEmpty ? null : rows.first;
  }

  // ── Meta ──────────────────────────────────────────────────────────────────

  Future<Map<String, dynamic>?> getPackageMeta() async {
    if (kIsWeb || _knowledgeDb == null) return null;
    try {
      final rows = await _knowledgeDb!.query('package_meta', limit: 1);
      return rows.isEmpty ? null : rows.first;
    } catch (_) {
      return null;
    }
  }

  // ── Tokenizer ─────────────────────────────────────────────────────────────

  List<String> _tokenize(String query, String language) {
    final cleaned = query.toLowerCase().trim();
    if (cleaned.isEmpty) return [];
    return cleaned
        .split(RegExp(r'[\s\u060C\u061B\u061F،؛؟,.!?;:()\[\]"]+'))
        .where((t) => t.length >= 2)
        .toList();
  }

  // ── Teardown ──────────────────────────────────────────────────────────────

  Future<void> close() async {
    await _knowledgeDb?.close();
    await _hazardDb?.close();
  }
}
