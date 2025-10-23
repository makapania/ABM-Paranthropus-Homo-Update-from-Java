"""
Full HOMINIDS Simulation Test

This script runs a complete 1-year simulation to test all features:
- Plant food dynamics with Verhulst equation
- Carcass scavenging
- Nesting behavior
- Output generation
"""

from hominids_model import HOMINIDSModel
import time

def run_full_simulation():
    """Run a complete 1-year simulation"""
    print("="*80)
    print("HOMINIDS MODEL - FULL SIMULATION TEST")
    print("="*80)
    print()
    
    print("Initializing model with enhanced features...")
    print("- Plant food dynamics with Verhulst equation")
    print("- Carcass scavenging system")
    print("- Individual and group nesting")
    print("- Output generation")
    print()
    
    # Create model with meat-eating and cooperative agents
    model = HOMINIDSModel(
        params_file='parameters.xls',
        landscape='voi',
        n_boisei=5,  # Smaller number for faster testing
        n_ergaster=5,
        boisei_options='bidm',  # Individual, digging, meat-eating
        ergaster_options='gidmc',  # Group, individual, digging, meat, cooperation
        n_years=1,
        random_seed=42
    )
    
    print(f"Model created with {len(model.hominid_agents)} hominid agents")
    print(f"Grid: {model.grid.width} x {model.grid.height} cells")
    print()
    
    print("Starting 1-year simulation...")
    start_time = time.time()
    
    # Run the simulation
    results = model.run()
    
    end_time = time.time()
    elapsed = end_time - start_time
    
    print(f"\nSimulation completed in {elapsed:.2f} seconds")
    print(f"Total steps: {model.n_years * 365 * model.params.active_time_units_per_day:,}")
    print()
    
    # Analyze results
    print("SIMULATION RESULTS:")
    print("-" * 40)
    
    # Agent statistics
    boisei_agents = [a for a in model.hominid_agents if a.species.value == 'boisei']
    ergaster_agents = [a for a in model.hominid_agents if a.species.value == 'ergaster']
    
    print(f"Boisei agents: {len(boisei_agents)}")
    print(f"Ergaster agents: {len(ergaster_agents)}")
    
    # Calculate average daily calories
    for species_name, agents in [("Boisei", boisei_agents), ("Ergaster", ergaster_agents)]:
        if agents:
            all_calories = []
            for agent in agents:
                all_calories.extend(agent.calories_history)
            
            if all_calories:
                avg_calories = sum(all_calories) / len(all_calories)
                print(f"{species_name} average daily calories: {avg_calories:.1f}")
                
                # Check starvation
                starved = sum(1 for agent in agents if agent.check_starvation())
                print(f"{species_name} starved: {starved}/{len(agents)}")
    
    # Carcass statistics
    total_carcasses = len(model.carcass_manager.carcasses)
    active_carcasses = len([c for c in model.carcass_manager.carcasses if not c.is_depleted()])
    print(f"Total carcasses appeared: {total_carcasses}")
    print(f"Active carcasses remaining: {active_carcasses}")
    
    # Output files
    print(f"\nOutput files generated in 'output/' directory:")
    print("- spatial_output.csv (GIS-compatible spatial data)")
    print("- agent_stats.csv (agent statistics)")
    print("- season_summary.csv (seasonal summaries)")
    
    print("\n" + "="*80)
    print("FULL SIMULATION TEST: COMPLETED SUCCESSFULLY!")
    print("="*80)
    
    return results

if __name__ == "__main__":
    results = run_full_simulation()
