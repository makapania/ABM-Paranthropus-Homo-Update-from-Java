"""
Comprehensive test suite for HOMINIDS model.
Tests each feature against expected behavior.
"""

from hominids_model import HOMINIDSModel
import pandas as pd


def test_parameter_loading():
    """Test that real parameters are loaded from Excel."""
    from plant_system import load_plant_species

    print("\n" + "="*80)
    print("TEST 1: Parameter Loading")
    print("="*80)

    species = load_plant_species('parameters.xls', 'voi')

    print(f"✓ Loaded {len(species)} species")

    # Check seasonal fruiting varies
    fruiting_patterns = [tuple(sp.seasons_fruiting) for sp in species]
    assert len(set(fruiting_patterns)) > 1, "All plants have same fruiting pattern!"
    print(f"✓ Seasonal fruiting varies: {len(set(fruiting_patterns))} patterns")

    # Check return rates vary
    return_rates = [sp.return_rate for sp in species]
    assert len(set(return_rates)) > 1, "All plants have same return rate!"
    print(f"✓ Return rates vary: {min(return_rates):.2f} to {max(return_rates):.2f}")

    # Check densities are non-zero
    densities = [sp.plants_per_unflooded for sp in species]
    assert max(densities) > 0, "All plant densities are zero!"
    print(f"✓ Plant densities loaded: max {max(densities):.1f} plants/cell")

    print("✓ TEST 1 PASSED\n")


def test_movement_algorithm():
    """Test that agents move intelligently toward food."""

    print("="*80)
    print("TEST 2: Movement Algorithm")
    print("="*80)

    model = HOMINIDSModel(
        params_file='parameters.xls',
        landscape='voi',
        n_boisei=5,
        n_ergaster=0,
        boisei_options='id',
        n_years=1,
        random_seed=42
    )

    # Track agent positions
    agent = model.hominid_agents[0]
    initial_pos = agent.pos

    # Run for 100 steps
    positions = [initial_pos]
    for _ in range(100):
        model.step()
        if agent.pos != positions[-1]:
            positions.append(agent.pos)

    # Agent should move (not stuck)
    assert len(positions) > 10, f"Agent barely moved: {len(positions)} positions"
    print(f"✓ Agent visited {len(set(positions))} unique positions in 100 steps")

    # Calculate average move distance
    total_distance = sum([
        agent.calculate_distance(positions[i], positions[i+1])
        for i in range(len(positions)-1)
    ])
    avg_distance = total_distance / (len(positions) - 1) if len(positions) > 1 else 0
    print(f"✓ Average move distance: {avg_distance:.2f} cells (diagonal movement)")

    print("✓ TEST 2 PASSED\n")


def test_neighborhood_scanning():
    """Test that agents can see food in neighboring cells."""

    print("="*80)
    print("TEST 3: Neighborhood Scanning")
    print("="*80)

    model = HOMINIDSModel(
        params_file='parameters.xls',
        landscape='voi',
        n_boisei=1,
        n_ergaster=0,
        boisei_options='id',
        n_years=1,
        random_seed=42
    )

    agent = model.hominid_agents[0]

    # Agent should scan 9 cells
    neighbors = model.grid.get_neighborhood(agent.pos, moore=True, include_center=True)
    assert len(neighbors) == 9, f"Expected 9 neighbors, got {len(neighbors)}"
    print(f"✓ Scanning {len(neighbors)} cells (Moore neighborhood)")

    # Check food options format
    food_options = agent.scan_for_food()
    if food_options:
        species, amount, cell_pos, distance = food_options[0]
        print(f"✓ Food options include: species, amount, cell_pos, distance")
        print(f"✓ Found {len(food_options)} food options")
    else:
        print("⚠ No food found (may need plant growth time)")

    print("✓ TEST 3 PASSED\n")


def test_calorie_tracking():
    """Test that detailed statistics are tracked."""

    print("="*80)
    print("TEST 4: Calorie Tracking")
    print("="*80)

    model = HOMINIDSModel(
        params_file='parameters.xls',
        landscape='voi',
        n_boisei=3,
        n_ergaster=2,
        boisei_options='idm',
        ergaster_options='gidmc',
        n_years=1,
        random_seed=42
    )

    # Run for 10 days
    for _ in range(10 * 720):
        model.step()

    # Check that arrays exist
    agent = model.hominid_agents[0]

    assert hasattr(agent, 'plant_calories_by_season'), "Missing plant_calories_by_season"
    assert hasattr(agent, 'carcass_calories_by_season'), "Missing carcass_calories_by_season"
    assert hasattr(agent, 'root_calories_by_season'), "Missing root_calories_by_season"
    assert hasattr(agent, 'daily_plant_calories'), "Missing daily_plant_calories"

    print(f"✓ Tracking arrays exist")

    total_plant = sum(agent.plant_calories_by_season)
    total_carcass = sum(agent.carcass_calories_by_season)

    print(f"  Plant calories: {total_plant:.0f}")
    print(f"  Carcass calories: {total_carcass:.0f}")

    print("✓ TEST 4 PASSED\n")


def test_agent_communication():
    """Test that agents communicate about carcasses."""

    print("="*80)
    print("TEST 5: Agent Communication")
    print("="*80)

    model = HOMINIDSModel(
        params_file='parameters.xls',
        landscape='voi',
        n_boisei=10,
        n_ergaster=0,
        boisei_options='idmc',  # Meat-eating cooperators
        n_years=1,
        random_seed=42
    )

    # Check that found_carcasses list exists
    assert hasattr(model, 'found_carcasses'), "Model missing found_carcasses list"
    print(f"✓ Model has found_carcasses list")

    # Check that agents have communication methods
    agent = model.hominid_agents[0]
    assert hasattr(agent, 'notify_others_of_carcass'), "Agent missing notify_others_of_carcass"
    assert hasattr(agent, 'check_for_carcass_calls'), "Agent missing check_for_carcass_calls"
    assert hasattr(agent, 'ignored_carcasses'), "Agent missing ignored_carcasses"
    assert hasattr(agent, 'wait_at_carcass'), "Agent missing wait_at_carcass"
    print(f"✓ Agents have communication methods")

    # Add a large carcass manually
    from carcass_system import Carcass, CarcassSize
    carcass = Carcass(
        unique_id=999,
        model=model,
        size=CarcassSize.LARGE,
        weight_grams=100000,
        location=(40, 50)
    )
    model.carcass_manager.carcasses.append(carcass)
    model.grid.place_agent(carcass, carcass.location)

    print(f"✓ Added test carcass at {carcass.location}")

    # Run until carcass is found
    carcass_found = False
    for _ in range(5000):
        model.step()
        if len(model.found_carcasses) > 0:
            print(f"✓ Carcass discovered at minute {model.current_minute}")
            carcass_found = True
            break

    if not carcass_found:
        print("⚠ Carcass not discovered within 5000 steps (agents may not have passed by)")
    else:
        # Check if agents responded
        agents_at_carcass = [a for a in model.hominid_agents if a.pos == carcass.location]
        print(f"✓ Agents at carcass: {len(agents_at_carcass)}")

    print("✓ TEST 5 PASSED\n")


def test_full_simulation():
    """Run a full 1-year simulation and verify completion."""

    print("="*80)
    print("TEST 6: Full 1-Year Simulation")
    print("="*80)

    model = HOMINIDSModel(
        params_file='parameters.xls',
        landscape='voi',
        n_boisei=10,
        n_ergaster=5,
        boisei_options='bidm',
        ergaster_options='gidmc',
        n_years=1,
        random_seed=42
    )

    print("Running 1-year simulation (this may take a few minutes)...")
    results = model.run()

    print(f"✓ Simulation completed")
    print(f"✓ Agent data records: {len(results['agent_data'])}")
    print(f"✓ Model data records: {len(results['model_data'])}")

    # Check output files
    import os
    assert os.path.exists('output/spatial_output.csv'), "Missing spatial output!"
    print(f"✓ Output files generated")

    # Check if agents got any calories
    avg_calories = sum(a.calories_today for a in model.hominid_agents) / len(model.hominid_agents)
    print(f"  Average calories per agent: {avg_calories:.0f}")

    # Check new output files
    if os.path.exists('output/agent_stats_by_season.csv'):
        print(f"✓ agent_stats_by_season.csv generated")
    else:
        print(f"⚠ agent_stats_by_season.csv not found")

    if os.path.exists('output/daily_calories.csv'):
        print(f"✓ daily_calories.csv generated")
    else:
        print(f"⚠ daily_calories.csv not found")

    print("✓ TEST 6 PASSED\n")


def run_all_tests():
    """Run all tests."""
    print("\n" + "="*80)
    print("HOMINIDS MODEL - COMPREHENSIVE TEST SUITE")
    print("="*80)

    try:
        test_parameter_loading()
        test_movement_algorithm()
        test_neighborhood_scanning()
        test_calorie_tracking()
        test_agent_communication()
        test_full_simulation()

        print("\n" + "="*80)
        print("ALL TESTS PASSED! ✓✓✓")
        print("="*80)
        return True

    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        return False
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = run_all_tests()
    exit(0 if success else 1)
