import 'package:flutter/material.dart';

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

// ---------- Sample data (you can expand later) ----------

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
      if (a.priority != b.priority) {
        return a.priority.compareTo(b.priority);
      }
      return b.confidence.compareTo(a.confidence);
    });

    final selected = <SafeBagItem>[];
    double runningCost = 0.0;

    for (final item in sorted) {
      final itemCost = item.cost;
      if (runningCost + itemCost <= budget) {
        selected.add(item);
        runningCost += itemCost;
      }
    }

    return SafeBagPlan(
      selectedItems: selected,
      totalCost: runningCost,
      remainingBudget: budget - runningCost,
    );
  }
}

// ---------- UI ----------

class GoBagScreen extends StatefulWidget {
  const GoBagScreen({super.key});

  @override
  State<GoBagScreen> createState() => _GoBagScreenState();
}

class _GoBagScreenState extends State<GoBagScreen> {
  final _budgetController = TextEditingController(text: '2000');
  late SafeBagPlan _plan;

  @override
  void initState() {
    super.initState();
    _recomputePlan();
  }

  void _recomputePlan() {
    final budget = double.tryParse(_budgetController.text) ?? 0.0;
    _plan = SafeBagPlanner.createPlan(budget: budget, householdSize: 1);
  }

  @override
  void dispose() {
    _budgetController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Safe Bag Planner'),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              'Enter your total budget for disaster preparedness (PKR):',
              style: TextStyle(fontSize: 14),
            ),
            const SizedBox(height: 8),
            TextField(
              controller: _budgetController,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(
                labelText: 'Budget (PKR)',
                border: OutlineInputBorder(),
              ),
              onChanged: (_) => setState(_recomputePlan),
            ),
            const SizedBox(height: 16),
            Text(
              'Recommended items for your family:',
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
                    final item = _plan.selectedItems[index];
                    return _ItemCard(item: item);
                  },
                ),
              ),
            const Divider(),
            Text(
              'Total cost: ${_plan.totalCost.toStringAsFixed(0)} PKR\n'
              'Remaining budget: ${_plan.remainingBudget.toStringAsFixed(0)} PKR',
              style: Theme.of(context).textTheme.bodyLarge,
            ),
          ],
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
      margin: const EdgeInsets.symmetric(vertical: 6),
      child: ExpansionTile(
        title: Text(item.name),
        subtitle: Text(
          '${item.category} • ${item.cost.toStringAsFixed(0)} PKR • Priority ${item.priority}',
        ),
        children: [
          Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _RowLabelValue('Why this item?', item.reason),
                const SizedBox(height: 8),
                _RowLabelValue('Evidence', item.evidence),
                const SizedBox(height: 8),
                _RowLabelValue(
                  'Confidence',
                  '${(item.confidence * 100).toStringAsFixed(0)}%',
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _RowLabelValue extends StatelessWidget {
  final String label;
  final String value;

  const _RowLabelValue(this.label, this.value);

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 4),
        Text(value),
      ],
    );
  }
}