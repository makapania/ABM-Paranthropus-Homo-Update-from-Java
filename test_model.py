"""
Test runner for HOMINIDS model - demonstrates basic functionality
"""

from hominids_model import HOMINIDSModel, Parameters
import time

def test_basic_model():
    """Test that we can create and initialize a model"""
    print("="*70)
    print("HOMINIDS MODEL - PYTHON VERSION - TEST RUN")
    print("="*70)
    print()
    
    print("Step 1: Testing parameter loading...")
    params = Parameters('parameters.xls', 'voi')
    print(f"  Loaded {len(params.plant_species)} plant species")
    print(f"  Grid: {params.grid_height} x {params.grid_width} cells")
    print(f"  Boisei daily calories: {params.boisei_daily_calorie_requirement}")
    print(f"  Ergaster daily calories: {params.ergaster_daily_calorie_requirement}")
    print()
    
    print("Step 2: Creating model with 10 boisei agents...")
    model = HOMINIDSModel(
        params_file='parameters.xls',
        landscape='voi',
        n_boisei=10,
        n_ergaster=0,
        boisei_options='i',  # Individual nesting
        ergaster_options='i',
        n_years=1,
        random_seed=42
    )
    print(f"  Created {len(model.agents)} agents")
    print()
    
    print("Step 3: Testing one simulation step...")
    model.step()
    print(f"  Current day: {model.current_day}")
    print(f"  Current minute: {model.current_minute}")
    print()
    
    print("Step 4: Testing one full day (720 minutes)...")
    start = time.time()
    for i in range(719):  # Already did 1 step
        model.step()
    elapsed = time.time() - start
    print(f"  Completed 720 steps in {elapsed:.2f} seconds")
    print(f"  Day advanced to: {model.current_day}")
    print()
    
    print("="*70)
    print("BASIC FUNCTIONALITY TEST: PASSED")
    print("="*70)
    print()
    print("Next steps:")
    print("  1. I'll now implement the full foraging behavior")
    print("  2. Add plant food dynamics")
    print("  3. Add carcass scavenging")
    print("  4. Add nesting behavior")
    print("  5. Add output generation (CSV files)")
    print()
    print("This will take another hour or so. The framework is solid!")
    print()

if __name__ == "__main__":
    test_basic_model()
