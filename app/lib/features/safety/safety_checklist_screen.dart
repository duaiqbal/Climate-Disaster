import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'dart:convert';
import '../../core/localization/app_localizations.dart';
import '../../core/theme/app_theme.dart';

// ─── Data model ───────────────────────────────────────────────────────────────

class ChecklistItem {
  final String id;
  final String text;
  bool checked;

  ChecklistItem(
      {required this.id, required this.text, this.checked = false});

  ChecklistItem copyWith({bool? checked}) =>
      ChecklistItem(id: id, text: text, checked: checked ?? this.checked);
}

class ChecklistCategory {
  final String id;
  final IconData icon;
  final Color color;
  final String titleKey;
  final List<ChecklistItem> items;

  const ChecklistCategory({
    required this.id,
    required this.icon,
    required this.color,
    required this.titleKey,
    required this.items,
  });
}

// ─── Screen ───────────────────────────────────────────────────────────────────

class SafetyChecklistScreen extends StatefulWidget {
  const SafetyChecklistScreen({super.key});

  @override
  State<SafetyChecklistScreen> createState() =>
      _SafetyChecklistScreenState();
}

class _SafetyChecklistScreenState extends State<SafetyChecklistScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabCtrl;
  late List<ChecklistCategory> _categories;
  static const String _prefKey = 'checklist_state';

  @override
  void initState() {
    super.initState();
    _buildCategories();
    _tabCtrl = TabController(length: _categories.length, vsync: this);
    _loadState();
  }

  void _buildCategories() {
    _categories = [
      ChecklistCategory(
        id: 'go_bag',
        icon: Icons.backpack_rounded,
        color: AppColors.primary,
        titleKey: 'checklist_go_bag',
        items: [
          ChecklistItem(id: 'gb1', text: 'Water (3 litres per person per day, 3-day supply)'),
          ChecklistItem(id: 'gb2', text: 'Non-perishable food (3-day supply)'),
          ChecklistItem(id: 'gb3', text: 'First aid kit with manual'),
          ChecklistItem(id: 'gb4', text: 'Torch / flashlight with extra batteries'),
          ChecklistItem(id: 'gb5', text: 'Whistle to signal for help'),
          ChecklistItem(id: 'gb6', text: 'Dust mask or cotton fabric (filter air)'),
          ChecklistItem(id: 'gb7', text: 'Plastic sheeting and duct tape'),
          ChecklistItem(id: 'gb8', text: 'Moist towelettes, garbage bags, twist ties'),
          ChecklistItem(id: 'gb9', text: 'Wrench or pliers to turn off utilities'),
          ChecklistItem(id: 'gb10', text: 'Manual can opener'),
          ChecklistItem(id: 'gb11', text: 'Local maps (printed)'),
          ChecklistItem(id: 'gb12', text: 'Cell phone with charger and backup battery'),
          ChecklistItem(id: 'gb13', text: 'Important documents (copies): NIC, land papers, medical'),
          ChecklistItem(id: 'gb14', text: 'Cash in small bills'),
          ChecklistItem(id: 'gb15', text: 'Emergency contact list (written, not only on phone)'),
          ChecklistItem(id: 'gb16', text: 'Warm clothing and sturdy shoes per family member'),
          ChecklistItem(id: 'gb17', text: 'Blankets or sleeping bags'),
          ChecklistItem(id: 'gb18', text: 'Prescription medications (7-day supply)'),
          ChecklistItem(id: 'gb19', text: 'Infant supplies (if applicable)'),
          ChecklistItem(id: 'gb20', text: 'Pet supplies (if applicable)'),
        ],
      ),
      ChecklistCategory(
        id: 'flood',
        icon: Icons.water_rounded,
        color: AppColors.ndmaColor,
        titleKey: 'checklist_flood',
        items: [
          ChecklistItem(id: 'fl1', text: 'Know your evacuation route to higher ground'),
          ChecklistItem(id: 'fl2', text: 'Store valuables and documents above floor level'),
          ChecklistItem(id: 'fl3', text: 'Know how to turn off electricity, gas, and water'),
          ChecklistItem(id: 'fl4', text: 'Never walk or drive through floodwater'),
          ChecklistItem(id: 'fl5', text: 'Avoid bridges over fast-moving water'),
          ChecklistItem(id: 'fl6', text: 'If caught in rising water, move to upper floors'),
          ChecklistItem(id: 'fl7', text: 'Do not return until authorities declare it safe'),
          ChecklistItem(id: 'fl8', text: 'Avoid floodwater — it may be contaminated'),
          ChecklistItem(id: 'fl9', text: 'Listen to NDMA/PDMA advisories on radio'),
          ChecklistItem(id: 'fl10', text: 'Help neighbours (elderly, disabled) evacuate'),
        ],
      ),
      ChecklistCategory(
        id: 'landslide',
        icon: Icons.landslide_rounded,
        color: AppColors.hazardHigh,
        titleKey: 'checklist_landslide',
        items: [
          ChecklistItem(id: 'ls1', text: 'Know warning signs: cracks in ground, leaning trees'),
          ChecklistItem(id: 'ls2', text: 'Listen for unusual sounds — snapping trees, rumbling'),
          ChecklistItem(id: 'ls3', text: 'Avoid steep slopes and drainages during heavy rain'),
          ChecklistItem(id: 'ls4', text: 'Evacuate immediately if you suspect a landslide'),
          ChecklistItem(id: 'ls5', text: 'Stay away from landslide path — re-activation risk'),
          ChecklistItem(id: 'ls6', text: 'Report cracks or land movement to local authorities'),
          ChecklistItem(id: 'ls7', text: 'Plant vegetation to stabilise slopes around home'),
          ChecklistItem(id: 'ls8', text: 'Do not build on steep, unstable slopes'),
          ChecklistItem(id: 'ls9', text: 'Check if your house has drainage channels'),
          ChecklistItem(id: 'ls10', text: 'Keep emergency contacts (PDMA KP: 1700)'),
        ],
      ),
      ChecklistCategory(
        id: 'evacuation',
        icon: Icons.exit_to_app_rounded,
        color: AppColors.hazardMedium,
        titleKey: 'checklist_evacuation',
        items: [
          ChecklistItem(id: 'ev1', text: 'Identify two evacuation routes from your home'),
          ChecklistItem(id: 'ev2', text: 'Identify meeting point outside home and outside neighbourhood'),
          ChecklistItem(id: 'ev3', text: 'Practice evacuation drill with all family members'),
          ChecklistItem(id: 'ev4', text: 'Identify a contact person outside affected area'),
          ChecklistItem(id: 'ev5', text: 'Know the location of nearest relief camp / shelter'),
          ChecklistItem(id: 'ev6', text: 'Ensure all family members know the plan'),
          ChecklistItem(id: 'ev7', text: 'Assign roles (who carries go-bag, who helps elderly)'),
          ChecklistItem(id: 'ev8', text: 'Keep vehicle fuel level above half when risk is high'),
          ChecklistItem(id: 'ev9', text: 'Know alternate routes if roads are blocked'),
          ChecklistItem(id: 'ev10', text: 'Leave early — do not wait until last moment'),
        ],
      ),
    ];
  }

  Future<void> _loadState() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_prefKey);
    if (raw == null) return;
    try {
      final Map<String, dynamic> saved = jsonDecode(raw);
      setState(() {
        for (final cat in _categories) {
          for (final item in cat.items) {
            item.checked = saved['${cat.id}_${item.id}'] == true;
          }
        }
      });
    } catch (_) {}
  }

  Future<void> _saveState() async {
    final prefs = await SharedPreferences.getInstance();
    final Map<String, bool> data = {};
    for (final cat in _categories) {
      for (final item in cat.items) {
        data['${cat.id}_${item.id}'] = item.checked;
      }
    }
    await prefs.setString(_prefKey, jsonEncode(data));
  }

  void _toggle(int catIndex, int itemIndex) {
    setState(() {
      _categories[catIndex].items[itemIndex].checked =
          !_categories[catIndex].items[itemIndex].checked;
    });
    _saveState();
  }

  void _resetCategory(int catIndex) {
    setState(() {
      for (final item in _categories[catIndex].items) {
        item.checked = false;
      }
    });
    _saveState();
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);

    return Scaffold(
      appBar: AppBar(
        title: Text(loc.safetyChecklist),
        bottom: TabBar(
          controller: _tabCtrl,
          isScrollable: true,
          indicatorColor: Colors.white,
          labelColor: Colors.white,
          unselectedLabelColor: Colors.white60,
          tabs: _categories
              .map((c) => Tab(
                    icon: Icon(c.icon, size: 18),
                    text: loc.translate(c.titleKey),
                  ))
              .toList(),
        ),
      ),
      body: TabBarView(
        controller: _tabCtrl,
        children: _categories
            .asMap()
            .entries
            .map((e) => _CategoryTab(
                  category: e.value,
                  catIndex: e.key,
                  onToggle: _toggle,
                  onReset: _resetCategory,
                  loc: loc,
                ))
            .toList(),
      ),
    );
  }

  @override
  void dispose() {
    _tabCtrl.dispose();
    super.dispose();
  }
}

class _CategoryTab extends StatelessWidget {
  final ChecklistCategory category;
  final int catIndex;
  final void Function(int, int) onToggle;
  final void Function(int) onReset;
  final AppLocalizations loc;

  const _CategoryTab({
    required this.category,
    required this.catIndex,
    required this.onToggle,
    required this.onReset,
    required this.loc,
  });

  @override
  Widget build(BuildContext context) {
    final checked = category.items.where((i) => i.checked).length;
    final total = category.items.length;
    final progress = total == 0 ? 0.0 : checked / total;

    return Column(
      children: [
        // Progress header
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
          color: category.color.withValues(alpha: 0.06),
          child: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '$checked / $total items completed',
                      style: const TextStyle(
                          fontSize: 12, color: AppColors.textMuted),
                    ),
                    const SizedBox(height: 4),
                    LinearProgressIndicator(
                      value: progress,
                      backgroundColor: Colors.grey.shade200,
                      color: category.color,
                      minHeight: 6,
                      borderRadius: BorderRadius.circular(3),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 12),
              TextButton.icon(
                onPressed: () => onReset(catIndex),
                icon: const Icon(Icons.restart_alt, size: 16),
                label: const Text('Reset', style: TextStyle(fontSize: 12)),
                style: TextButton.styleFrom(
                    foregroundColor: AppColors.textMuted),
              ),
            ],
          ),
        ),

        // Items list
        Expanded(
          child: ListView.separated(
            padding: const EdgeInsets.symmetric(vertical: 8),
            itemCount: category.items.length,
            separatorBuilder: (_, __) =>
                const Divider(height: 1, indent: 56),
            itemBuilder: (_, i) {
              final item = category.items[i];
              return ListTile(
                leading: GestureDetector(
                  onTap: () => onToggle(catIndex, i),
                  child: AnimatedContainer(
                    duration: const Duration(milliseconds: 200),
                    width: 24,
                    height: 24,
                    decoration: BoxDecoration(
                      color: item.checked ? category.color : Colors.white,
                      shape: BoxShape.circle,
                      border: Border.all(
                        color: item.checked
                            ? category.color
                            : Colors.grey.shade400,
                        width: 2,
                      ),
                    ),
                    child: item.checked
                        ? const Icon(Icons.check,
                            size: 14, color: Colors.white)
                        : null,
                  ),
                ),
                title: Text(
                  item.text,
                  style: TextStyle(
                    fontSize: 13,
                    height: 1.4,
                    color: item.checked
                        ? AppColors.textMuted
                        : AppColors.textDark,
                    decoration: item.checked
                        ? TextDecoration.lineThrough
                        : null,
                  ),
                ),
                onTap: () => onToggle(catIndex, i),
              );
            },
          ),
        ),
      ],
    );
  }
}
