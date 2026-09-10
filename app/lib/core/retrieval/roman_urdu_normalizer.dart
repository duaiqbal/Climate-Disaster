/// Normalizes Roman Urdu spelling variants so that keyword retrieval
/// works across the many ways Roman Urdu is written informally.
///
/// Strategy: expand a query term into all known variant spellings.
/// This avoids lossy single-form collapse and improves recall.
class RomanUrduNormalizer {
  RomanUrduNormalizer._();

  // ─── Variant map ──────────────────────────────────────────────────────────
  // Each canonical form maps to a list of known spelling variants.
  static const Map<String, List<String>> _variants = {
    'saib': ['saib', 'sab', 'sayl', 'sail'],
    'selab': ['selab', 'sailab', 'sailab', 'salab'],
    'flood': ['flood', 'floood'],
    'baarish': ['baarish', 'barish', 'baarsh'],
    'paani': ['paani', 'pani', 'paanee'],
    'khatar': ['khatar', 'khatara', 'khatra'],
    'zameeni': ['zameeni', 'zamini', 'zameen'],
    'khiskaao': ['khiskaao', 'khiskaav', 'khiskaav', 'khiskaana'],
    'darya': ['darya', 'dariya', 'nehri'],
    'nichle': ['nichle', 'neeche', 'neechay'],
    'evacuation': ['evacuation', 'nikalna', 'nikalo', 'bhaago'],
    'mehfooz': ['mehfooz', 'mehfuz', 'mahfuz'],
    'bachao': ['bachao', 'bachaao', 'bachana'],
    'madad': ['madad', 'help', 'imdaad'],
    'hifazat': ['hifazat', 'hifaazat', 'hifaazti'],
    'raasta': ['raasta', 'rasta', 'raah'],
    'ghar': ['ghar', 'makan', 'makaan'],
    'pahaar': ['pahaar', 'pahar', 'parbat'],
    'nadi': ['nadi', 'nehri', 'nahar'],
    'barfaab': ['barfaab', 'barfab', 'glof'],
    'aasman': ['aasman', 'bijli', 'toofan'],
    'toofan': ['toofan', 'tufan', 'andhi'],
    'alert': ['alert', 'khabardar', 'agaah'],
    'taiyaari': ['taiyaari', 'taiyyari', 'preparation'],
    'zaroori': ['zaroori', 'zaruri', 'important'],
    'foran': ['foran', 'jaldi', 'abhi'],
    'suraksha': ['suraksha', 'surakhsha', 'hifazat'],
  };

  /// Returns all spelling variants for all tokens in the query.
  /// Tokens not in the map are returned as-is.
  static List<String> expandQuery(String romanUrduQuery) {
    final tokens = romanUrduQuery.toLowerCase().split(RegExp(r'\s+'));
    final expanded = <String>{};

    for (final token in tokens) {
      if (token.isEmpty) continue;
      bool found = false;
      for (final entry in _variants.entries) {
        if (entry.value.contains(token)) {
          expanded.addAll(entry.value);
          found = true;
          break;
        }
      }
      if (!found) expanded.add(token);
    }

    return expanded.toList();
  }

  /// Normalizes a single term to its canonical key (if known).
  static String canonicalize(String term) {
    final lower = term.toLowerCase();
    for (final entry in _variants.entries) {
      if (entry.value.contains(lower)) return entry.key;
    }
    return lower;
  }

  /// Returns true if the string contains predominantly Roman Urdu vocabulary.
  static bool isLikelyRomanUrdu(String text) {
    final lower = text.toLowerCase();
    final allVariants = _variants.values.expand((v) => v).toSet();
    final tokens = lower.split(RegExp(r'\s+'));
    final matchCount = tokens.where((t) => allVariants.contains(t)).length;
    return tokens.isNotEmpty && matchCount / tokens.length >= 0.25;
  }
}
