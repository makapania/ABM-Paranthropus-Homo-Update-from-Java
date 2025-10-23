"""
Output Generator for HOMINIDS Model

This module generates GIS-compatible CSV output files matching the original format.
"""

import csv
import os
from typing import Dict, List, Tuple
import pandas as pd


def generate_spatial_csv(model, filename: str = "spatial_output.csv"):
    """
    Create GIS CSV with spatial data by cell.
    
    Args:
        model: The HOMINIDSModel instance
        filename: Output filename
    """
    print(f"Generating spatial CSV: {filename}")
    
    # Collect data for each cell
    cell_data = {}
    
    # Initialize all cells
    for x in range(model.grid.width):
        for y in range(model.grid.height):
            cell_data[(x, y)] = {
                'gridcode': x * model.grid.height + y,
                'X': x,
                'Y': y,
                'Bcal0': 0, 'Bcal1': 0, 'Bcal2': 0, 'Bcal3': 0, 'Bcal4': 0,
                'Ecal0': 0, 'Ecal1': 0, 'Ecal2': 0, 'Ecal3': 0, 'Ecal4': 0,
                'BscanF': 0, 'EscanF': 0,
                'Btravel': 0, 'Etravel': 0,
                'Bnest': 0, 'Enest': 0,
                'S1': 0, 'S2': 0, 'S3': 0, 'S4': 0
            }
    
    # Process agent activity logs
    for agent in model.hominid_agents:
        if not hasattr(agent, 'activity_log'):
            continue
            
        species_prefix = 'B' if agent.species.value == 'boisei' else 'E'
        
        for pos, activities in agent.activity_log.items():
            if pos in cell_data:
                # Eating time
                eating_time = activities.get('eating', 0)
                cell_data[pos][f'{species_prefix}cal0'] += eating_time
                
                # Traveling time
                travel_time = activities.get('traveling', 0)
                cell_data[pos][f'{species_prefix}travel'] += travel_time
                
                # Scanning time (simplified - assume 1 scan per minute active)
                scan_time = eating_time + travel_time
                cell_data[pos][f'{species_prefix}scanF'] += scan_time
    
    # Process nesting locations
    for agent in model.hominid_agents:
        if hasattr(agent, 'nest_location') and agent.nest_location:
            species_prefix = 'B' if agent.species.value == 'boisei' else 'E'
            pos = agent.nest_location
            if pos in cell_data:
                cell_data[pos][f'{species_prefix}nest'] = 1
    
    # Process seasonal data (simplified)
    for pos in cell_data:
        if model.current_season == 1:
            cell_data[pos]['S1'] = 1
        elif model.current_season == 2:
            cell_data[pos]['S2'] = 1
        elif model.current_season == 3:
            cell_data[pos]['S3'] = 1
        else:
            cell_data[pos]['S4'] = 1
    
    # Write CSV file
    with open(filename, 'w', newline='') as csvfile:
        fieldnames = [
            'gridcode', 'X', 'Y',
            'Bcal0', 'Bcal1', 'Bcal2', 'Bcal3', 'Bcal4',
            'Ecal0', 'Ecal1', 'Ecal2', 'Ecal3', 'Ecal4',
            'BscanF', 'EscanF',
            'Btravel', 'Etravel',
            'Bnest', 'Enest',
            'S1', 'S2', 'S3', 'S4'
        ]
        
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for pos, data in cell_data.items():
            writer.writerow(data)
    
    print(f"  Generated {len(cell_data)} cell records")


def generate_agent_stats(model, filename: str = "agent_stats.csv"):
    """
    Create agent statistics file.
    
    Args:
        model: The HOMINIDSModel instance
        filename: Output filename
    """
    print(f"Generating agent stats CSV: {filename}")
    
    agent_data = []
    
    for agent in model.hominid_agents:
        # Calculate average daily calories
        if len(agent.calories_history) > 0:
            avg_calories = sum(agent.calories_history) / len(agent.calories_history)
        else:
            avg_calories = 0
        
        # Check if agent starved
        starved = agent.check_starvation() if hasattr(agent, 'check_starvation') else False
        
        agent_data.append({
            'AgentID': agent.unique_id,
            'Species': agent.species.value,
            'Day': model.current_day,
            'Calories': avg_calories,
            'Starved': 1 if starved else 0,
            'CanDig': 1 if agent.can_dig else 0,
            'CanEatMeat': 1 if agent.can_eat_meat else 0,
            'Cooperates': 1 if agent.cooperates else 0,
            'GroupNesting': 1 if agent.group_nesting else 0
        })
    
    # Write CSV file
    with open(filename, 'w', newline='') as csvfile:
        fieldnames = [
            'AgentID', 'Species', 'Day', 'Calories', 'Starved',
            'CanDig', 'CanEatMeat', 'Cooperates', 'GroupNesting'
        ]
        
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for data in agent_data:
            writer.writerow(data)
    
    print(f"  Generated {len(agent_data)} agent records")


def generate_season_summary(model, filename: str = "season_summary.csv"):
    """
    Create season summary file.
    
    Args:
        model: The HOMINIDSModel instance
        filename: Output filename
    """
    print(f"Generating season summary CSV: {filename}")
    
    # Calculate summary statistics
    boisei_agents = [a for a in model.hominid_agents if a.species.value == 'boisei']
    ergaster_agents = [a for a in model.hominid_agents if a.species.value == 'ergaster']
    
    def calc_avg_calories(agents):
        if not agents:
            return 0
        all_calories = []
        for agent in agents:
            all_calories.extend(agent.calories_history)
        return sum(all_calories) / len(all_calories) if all_calories else 0
    
    def calc_starved_count(agents):
        return sum(1 for agent in agents if agent.check_starvation())
    
    season_data = {
        'Season': model.current_season,
        'Day': model.current_day,
        'BoiseiCount': len(boisei_agents),
        'ErgasterCount': len(ergaster_agents),
        'BoiseiAvgCalories': calc_avg_calories(boisei_agents),
        'ErgasterAvgCalories': calc_avg_calories(ergaster_agents),
        'BoiseiStarved': calc_starved_count(boisei_agents),
        'ErgasterStarved': calc_starved_count(ergaster_agents),
        'TotalCarcasses': len(model.carcass_manager.carcasses),
        'ActiveCarcasses': len([c for c in model.carcass_manager.carcasses if not c.is_depleted()])
    }
    
    # Write CSV file
    with open(filename, 'w', newline='') as csvfile:
        fieldnames = [
            'Season', 'Day', 'BoiseiCount', 'ErgasterCount',
            'BoiseiAvgCalories', 'ErgasterAvgCalories',
            'BoiseiStarved', 'ErgasterStarved',
            'TotalCarcasses', 'ActiveCarcasses'
        ]
        
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(season_data)
    
    print(f"  Generated season summary for Season {model.current_season}")


def generate_all_outputs(model, output_dir: str = "output"):
    """
    Generate all output files.
    
    Args:
        model: The HOMINIDSModel instance
        output_dir: Directory to save output files
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"\nGenerating output files in {output_dir}/")
    print("="*50)
    
    # Generate all output files
    generate_spatial_csv(model, os.path.join(output_dir, "spatial_output.csv"))
    generate_agent_stats(model, os.path.join(output_dir, "agent_stats.csv"))
    generate_season_summary(model, os.path.join(output_dir, "season_summary.csv"))
    
    print("="*50)
    print("Output generation complete!")


if __name__ == "__main__":
    # Test the output generator
    print("Testing output generator...")
    
    # This would be called from the main model after simulation
    # generate_all_outputs(model, "test_output")
    print("Output generator ready for use with HOMINIDS model.")

