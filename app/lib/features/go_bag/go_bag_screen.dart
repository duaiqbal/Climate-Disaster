import 'package:flutter/material.dart';
import '../screen_entrance.dart';

// ---------- Models ----------
class SafeBagItem {
  final String id;
  final String name;
  final String category;
  final double cost;
  final int priority;
  final String reason;
  final String evidence;
  final double confidence;

  const SafeBagItem({
    required this.id,
    required this.name,
    required this.category,
    required this.cost,
    required this.priority,
    required this.reason,
    required this.evidence,
    required this.confidence,
  });
}

// ---------- Sample data ----------
class PreparednessItems {
  static const List<SafeBagItem> all = [
    SafeBagItem(
      id: 'water_5l',
      name: 'Drinking water (5L per person)',
      category: 'Water',
      cost: 300,
      priority: 1,
      reason:
          'Safe drinking water is the first need in any disaster; dehydration and waterborne diseases are major risks.',
      evidence: 'NDMA household preparedness guidelines',
      confidence: 0.95,
    ),
    SafeBagItem(
      id: 'docs_pack',
      name: 'Documents pack (CNIC, land records, medical)',
      category: 'Documents',
      cost: 0,
      priority: 1,
      reason:
          'Having key documents ready speeds up relief, evacuation, and recovery processes.',
      evidence: 'NDMA & PDMA community preparedness materials',
      confidence: 0.9,
    ),
    SafeBagItem(
      id: 'first_aid',
      name: 'Basic first aid kit',
      category: 'Medicine',
      cost: 800,
      priority: 2,
      reason:
          'Minor injuries are common during floods/landslides; immediate first aid reduces complications.',
      evidence: 'WHO basic emergency kit recommendations',
      confidence: 0.85,
    ),
    SafeBagItem(
      id: 'torch_bat',
      name: 'Torch + extra batteries',
      category: 'Light',
      cost: 600,
      priority: 2,
      reason:
          'Power outages are frequent in disasters; light is needed for safe movement at night.',
      evidence: 'NDMA household preparedness checklist',
      confidence: 0.8,
    ),
    SafeBagItem(
      id: 'rope_20m',
      name: '20m rope',
      category: 'Rescue',
      cost: 500,
      priority: 3,
      reason:
          'Useful for crossing water, securing loads, or basic rescue in flood/landslide scenarios.',
      evidence: 'AKAH community DRR trainings in Chitral',
      confidence: 0.75,
    ),
    SafeBagItem(
      id: 'warm_clothes',
      name: 'Warm clothes + rain poncho',
      category: 'Clothing',
      cost: 1200,
      priority: 2,
      reason:
          'Hypothermia is a major risk in Chitral mountains; waterproof clothing is essential.',
      evidence: 'NDMA National Disaster Response Plan 2024',
      confidence: 0.88,
    ),
    SafeBagItem(
      id: 'whistle',
      name: 'Emergency whistle',
      category: 'Signaling',
      cost: 100,
      priority: 2,
      reason:
          'A whistle can signal rescuers across long distances with minimal energy.',
      evidence: 'NDMA household preparedness checklist',
      confidence: 0.82,
    ),
    SafeBagItem(
      id: 'cash',
      name: 'Cash in small bills (PKR 2,000–5,000)',
      category: 'Finance',
      cost: 0,
      priority: 1,
      reason:
          'Digital payments fail during disasters; cash is needed for transport and supplies.',
      evidence: 'NDMA & PDMA community preparedness materials',
      confidence: 0.92,
    ),
    SafeBagItem(
      id: 'food_dry',
      name: 'Dry food (biscuits, dates, nuts — 3-day supply)',
      category: 'Food',
      cost: 500,
      priority: 1,
      reason:
          'Ready-to-eat food is critical for the first 72 hours before relief reaches affected areas.',
      evidence: 'NDMA National Monsoon Contingency Plan 2024',
      confidence: 0.93,
    ),
    SafeBagItem(
      id: 'medicine',
      name: 'Personal medications (7-day supply)',
      category: 'Medicine',
      cost: 0,
      priority: 1,
      reason:
          'Chronic medication access is interrupted during disasters; 7-day supply is standard.',
      evidence: 'WHO emergency preparedness guidelines',
      confidence: 0.9,
    ),
  ];
}

// ---------- Planner logic ----------
class SafeBagPlan {
  final List<SafeBagItem> selectedItems;
  final double totalCost;
  final double remainingBudget;

  const SafeBagPlan({
    required this.selectedItems,
    required this.totalCost,
    required this.remainingBudget,
  });
}

class SafeBagPlanner {
  static SafeBagPlan createPlan({
    required double budget,
    int householdSize = 1,
  }) {
    final sorted = List<SafeBagItem>.from(PreparednessItems.all);
    sorted.sort((a, b) {
      if (a.priority != b.priority) return a.priority.compareTo(b.priority);
      return b.confidence.compareTo(a.confidence);
    });

    final selected = <SafeBagItem>[];
    double runningCost = 0.0;

    for (final item in sorted) {
      if (runningCost + item.cost <= budget) {
        selected.add(item);
        runningCost += item.cost;
      }
    }

    return SafeBagPlan(
      selectedItems: selected,
      totalCost: runningCost,
      remainingBudget: budget - runningCost,
    );
  }
}

// ---------- Screen ----------
class GoBagScreen extends StatefulWidget {
  const GoBagScreen({super.key});

  @override
  State<GoBagScreen> createState() => _GoBagScreenState();
}

class _GoBagScreenState extends State<GoBagScreen> {
  final _budgetController = TextEditingController(text: '3000');
  late SafeBagPlan _plan;

  @override
  void initState() {
    super.initState();
    _recomputePlan();
  }

  void _recomputePlan() {
    final budget = double.tryParse(_budgetController.text) ?? 0.0;
    setState(() {
      _plan = SafeBagPlanner.createPlan(budget: budget);
    });
  }

  @override
  void dispose() {
    _budgetController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ScreenEntrance(
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Go Bag Planner'),
          backgroundColor: const Color(0xFF00695C),
          foregroundColor: Colors.white,
        ),
        body: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Info banner
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: const Color(0xFFFFF8E1),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(
                      color: const Color(0xFFFFA000).withValues(alpha: 0.4)),
                ),
                child: const Row(
                  children: [
                    Icon(Icons.info_outline,
                        color: Color(0xFFFFA000), size: 18),
                    SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'Items ranked by priority then confidence. '
                        'Sources: NDMA, PDMA KP, WHO.',
                        style:
                            TextStyle(fontSize: 12, color: Color(0xFF5D4037)),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),

              // Budget input
              const Text(
                'Enter your total budget for disaster preparedness (PKR):',
                style: TextStyle(fontSize: 14, fontWeight: FontWeight.w500),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _budgetController,
                keyboardType: TextInputType.number,
                decoration: InputDecoration(
                  labelText: 'Budget (PKR)',
                  prefixIcon: const Icon(Icons.currency_exchange),
                  border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(10)),
                ),
                onChanged: (_) => _recomputePlan(),
              ),
              const SizedBox(height: 16),

              Text(
                'Recommended items (${_plan.selectedItems.length} of ${PreparednessItems.all.length}):',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: 8),

              if (_plan.selectedItems.isEmpty)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 16),
                  child: Text(
                    'No items fit within this budget. Try increasing your budget.',
                    style: TextStyle(color: Colors.red),
                  ),
                )
              else
                Expanded(
                  child: ListView.builder(
                    itemCount: _plan.selectedItems.length,
                    itemBuilder: (context, index) {
                      return _ItemCard(item: _plan.selectedItems[index]);
                    },
                  ),
                ),

              const Divider(),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: const Color(0xFFE8F5E9),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Total cost: ${_plan.totalCost.toStringAsFixed(0)} PKR',
                      style: const TextStyle(
                          fontWeight: FontWeight.w700, fontSize: 15),
                    ),
                    Text(
                      'Remaining budget: ${_plan.remainingBudget.toStringAsFixed(0)} PKR',
                      style: const TextStyle(
                          fontSize: 13, color: Color(0xFF388E3C)),
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

class _ItemCard extends StatelessWidget {
  final SafeBagItem item;

  const _ItemCard({required this.item});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 5),
      child: ExpansionTile(
        leading: CircleAvatar(
          backgroundColor: const Color(0xFF00695C).withValues(alpha: 0.12),
          child: Text(
            '${item.priority}',
            style: const TextStyle(
                color: Color(0xFF00695C), fontWeight: FontWeight.w700),
          ),
        ),
        title: Text(item.name,
            style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
        subtitle: Text(
          '${item.category}  •  ${item.cost == 0 ? "Free" : "${item.cost.toStringAsFixed(0)} PKR"}  •  '
          'Confidence ${(item.confidence * 100).toStringAsFixed(0)}%',
          style: const TextStyle(fontSize: 12),
        ),
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _Row('Why this item?', item.reason),
                const SizedBox(height: 6),
                _Row('Evidence', item.evidence),
                const SizedBox(height: 6),
                Row(
                  children: [
                    const Text('Confidence: ',
                        style: TextStyle(
                            fontWeight: FontWeight.bold, fontSize: 13)),
                    LinearProgressIndicator(
                      value: item.confidence,
                      minHeight: 8,
                      backgroundColor: Colors.grey.shade200,
                      color: item.confidence >= 0.9
                          ? const Color(0xFF388E3C)
                          : item.confidence >= 0.75
                              ? const Color(0xFFF57C00)
                              : const Color(0xFFD32F2F),
                    ).apply(item.confidence),
                    const SizedBox(width: 8),
                    Text('${(item.confidence * 100).toStringAsFixed(0)}%',
                        style: const TextStyle(
                            fontWeight: FontWeight.w700, fontSize: 13)),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

extension _ProgressApply on LinearProgressIndicator {
  Widget apply(double val) => SizedBox(width: 80, child: this);
}

class _Row extends StatelessWidget {
  final String label;
  final String value;

  const _Row(this.label, this.value);

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label,
            style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
        const SizedBox(height: 3),
        Text(value, style: const TextStyle(fontSize: 13, height: 1.4)),
      ],
    );
  }
}
