# QUICK REFERENCE - HOMINIDS Model Implementation

## 🎯 Quick Status
- **Completion:** ~90%
- **Working:** Phases 1-3 (parameters, movement, scanning)
- **Remaining:** Phases 4-6 (communication, statistics, testing)
- **Time to complete:** 3-5 hours

## 🔧 Key Code Locations

### hominids_model.py
```python
# Line 201: Mesa 3.x Agent init fix
super().__init__(model)
self.unique_id = unique_id

# Lines 468-493: calculate_distance() - toroidal wrapping
# Lines 495-533: evaluate_cell_prospects() - food value
# Lines 535-609: move_toward_food() - intelligent movement
# Lines 611-660: _wander_to_distant_cell() - exploration

# Lines 292-345: scan_for_food() - 9-cell neighborhood
# Lines 419-459: choose_best_food() - prioritization
# Lines 259-300: step() - main agent behavior
```

### plant_system.py
```python
# Line 125: Store plant_species_list for seasonal checks
self.plant_species_list = plant_species_list

# Lines 165-171: Use real seasonal fruiting
species = next((s for s in self.plant_species_list if s.species_id == species_id), None)
if species:
    is_fruiting_season = species.seasons_fruiting[season - 1]

# Lines 261-269: safe_float helper function
# Lines 273-275: Map Excel column names to parameters
# Lines 277-285: Load seasonal fruiting patterns
# Lines 289-310: Load real return rate parameters
```

## 🐛 Critical Issue

**Agents not eating (0 calories)**

**Debug:**
```python
# Check plant food amounts
for species_id, amount in cell_food.food_amounts.items():
    print(f"{species_id}: {amount}")

# Check if plants are growing
# Run for 7 days instead of 1
for _ in range(7 * 720):
    model.step()
```

**Potential fixes:**
```python
# 1. Start with more food
self.food_amounts[species.species_id] = capacity * 0.5  # Not 0.01

# 2. Increase growth rate
r = 0.3  # Not 0.1

# 3. Check seasonal fruiting loaded correctly
print(species.seasons_fruiting)  # Should vary by species
```

## ✅ What's Working

```python
# Test 1: Parameters loaded
from plant_system import load_plant_species
species = load_plant_species('parameters.xls', 'voi')
print(f"Loaded {len(species)} species")
# Should print: "Loaded 27 species"

# Test 2: Movement intelligence
model = HOMINIDSModel('parameters.xls', 'voi', 5, 0, 'id', 1, 42)
agent = model.hominid_agents[0]
neighbors = model.grid.get_neighborhood(agent.pos, moore=True, include_center=True)
print(f"Scanning {len(neighbors)} cells")
# Should print: "Scanning 9 cells"

# Test 3: Neighborhood scanning
food_options = agent.scan_for_food()
print(f"Found {len(food_options)} food options")
# Returns: (species, amount, cell_pos, distance) tuples
```

## 📋 Next Tasks (Priority Order)

1. **Debug food availability** (30 min)
   - Add print statements in scan_for_food
   - Check plant growth over time
   - Verify seasonal fruiting

2. **Phase 4.1: Add found_carcasses list** (15 min)
   ```python
   # In HOMINIDSModel.__init__ line 655:
   self.found_carcasses = []

   # In HOMINIDSModel.step() line 755:
   self.found_carcasses = []
   ```

3. **Phase 4.2: Add notify method** (15 min)
   ```python
   def notify_others_of_carcass(self, carcass):
       if not self.cooperates:
           return
       if carcass not in self.model.found_carcasses:
           self.model.found_carcasses.append(carcass)
   ```

4. **Phase 4.3: Add earshot checking** (30 min)
   ```python
   def check_for_carcass_calls(self):
       # Check found_carcasses within earshot_distance
       # Return closest carcass
   ```

5. **Phase 5: Add tracking arrays** (30 min)
   ```python
   # In HominidAgent.__init__:
   self.plant_calories_by_season = [0.0] * n_seasons
   self.carcass_calories_by_season = [0.0] * n_seasons
   # Update in eat_food() and scavenge_carcass()
   ```

6. **Phase 6: Create test suite** (1 hour)
   ```python
   # Create test_full_model.py
   # Run all validation tests
   ```

## 🧪 Testing Commands

```bash
# Quick 1-day test
python3 -c "from hominids_model import HOMINIDSModel; m = HOMINIDSModel('parameters.xls', 'voi', 5, 0, 'id', 1, 42); [m.step() for _ in range(720)]; print(f'Avg: {sum(a.calories_today for a in m.hominid_agents)/5:.0f} kcal')"

# Test parameter loading
python3 -c "from plant_system import load_plant_species; s = load_plant_species('parameters.xls', 'voi'); print([sp.seasons_fruiting for sp in s[:5]])"

# Full 1-year simulation
python3 test_model.py
```

## 📖 Documentation Files

1. **AI_HANDOFF_PHASE_4-6.md** - Complete guide (READ THIS FIRST)
2. **SESSION_SUMMARY.md** - What was accomplished
3. **QUICK_REFERENCE.md** - This file (quick lookup)
4. **AI_HANDOFF_DOCUMENT.md** - Original plan
5. **COMPLETION_SUMMARY.md** - Previous status

## 🎯 Success Criteria

**Model is 100% complete when:**
- [ ] Agents eat food (>0 calories per day)
- [ ] Cooperators call each other to carcasses
- [ ] Statistics tracked by season and day
- [ ] All tests pass
- [ ] 1-year simulation runs without errors
- [ ] Output files generated correctly

## 💾 File Backup

Before making changes:
```bash
cp hominids_model.py hominids_model.py.backup
cp plant_system.py plant_system.py.backup
```

## 🚀 Quick Start for Next Session

```bash
# 1. Navigate to directory
cd /Users/mattsponheimer/git/ABM-Paranthropus-Homo-Update-from-Java

# 2. Read handoff document
# Open AI_HANDOFF_PHASE_4-6.md

# 3. Debug food availability
python3 << 'EOF'
from hominids_model import HOMINIDSModel
model = HOMINIDSModel('parameters.xls', 'voi', 1, 0, 'id', 1, 42)
agent = model.hominid_agents[0]
print("Initial scan:", len(agent.scan_for_food()), "foods")
for _ in range(720):
    model.step()
print("After 1 day:", len(agent.scan_for_food()), "foods")
print("Calories:", agent.calories_today)
EOF

# 4. Start Phase 4 implementation
# Follow AI_HANDOFF_PHASE_4-6.md Section 4
```

## 📞 Key Questions for User

1. Do you have original Java output files for validation?
2. What are expected calorie intakes for agents?
3. Should we increase initial food percentage?
4. Any specific validation criteria from research?

---

**For detailed implementation instructions, see AI_HANDOFF_PHASE_4-6.md**
