"""
Plant Food System for HOMINIDS Model

This module implements:
1. Plant species with seasonal fruiting
2. Verhulst population growth equation
3. Food availability by season and topography
4. Return rate calculations
"""

import numpy as np
from typing import Dict, List, Tuple
import xlrd


class PlantSpecies:
    """
    Represents a plant species with all its parameters.
    
    Each plant species has:
    - Seasonal fruiting patterns (4 seasons)
    - Different abundance in channel/flooded/unflooded zones
    - Caloric value and return rates
    - Visibility/detection probability
    - Tool requirements (digging for tubers)
    - Species-specific edibility
    """
    
    def __init__(self, species_id: int, name: str, params: dict):
        """
        Initialize a plant species.
        
        Args:
            species_id: Unique ID number
            name: Species name
            params: Dictionary of all plant parameters from Excel
        """
        self.species_id = species_id
        self.name = name
        
        # Basic properties
        self.disabled = params.get('disable', '') == 'Y'
        self.depends_on = params.get('depends_on', None)
        self.tools_required = params.get('tools_required', '') == 'Y'
        self.has_digging_phase = params.get('has_digging_phase', '') == 'Y'
        self.edible_by_boisei = params.get('edible_by_boisei', '') == 'Y'
        self.edible_by_ergaster = params.get('edible_by_ergaster', '') == 'Y'
        
        # Abundance by topography (plants per cell)
        self.plants_per_channel = params.get('plants_per_channel', 0.0)
        self.plants_per_flooded = params.get('plants_per_flooded', 0.0)
        self.plants_per_unflooded = params.get('plants_per_unflooded', 0.0)
        
        # Nesting tree
        self.is_nesting_tree = params.get('nesting_tree', '') == 'Y'
        
        # Food properties (will be loaded from additional columns)
        self.seasons_fruiting = params.get('seasons_fruiting', [False, False, False, False])
        self.grams_per_feeding_unit = params.get('grams_per_feeding_unit', 100.0)
        self.calories_per_gram = params.get('calories_per_gram', 1.0)
        self.visibility_probability = params.get('visibility_probability', 0.5)
        self.handling_time_minutes = params.get('handling_time_minutes', 1.0)
        
        # Return rate (calories per minute) - calculated
        self.return_rate = (self.grams_per_feeding_unit * self.calories_per_gram) / self.handling_time_minutes if self.handling_time_minutes > 0 else 0.0
    
    def is_fruiting(self, season: int) -> bool:
        """Check if this plant bears fruit in the given season (1-4)"""
        if season < 1 or season > 4:
            return False
        return self.seasons_fruiting[season - 1]
    
    def can_be_eaten_by(self, species_name: str, has_tools: bool) -> bool:
        """
        Check if this plant can be eaten by the given species.
        
        Args:
            species_name: 'boisei' or 'ergaster'
            has_tools: Whether agent has digging tools
            
        Returns:
            True if agent can eat this plant
        """
        # Check species edibility
        if species_name.lower() == 'boisei' and not self.edible_by_boisei:
            return False
        if species_name.lower() == 'ergaster' and not self.edible_by_ergaster:
            return False
        
        # Check tool requirements
        if self.tools_required and not has_tools:
            return False
        
        return not self.disabled
    
    def __repr__(self):
        return f"PlantSpecies({self.species_id}: {self.name}, RR={self.return_rate:.1f} kcal/min)"


from mesa import Agent, Model

class CellFood(Agent):
    """
    Manages food availability in a single grid cell.
    
    This tracks:
    - Which plant species are present
    - Current food availability (grows/decays seasonally)
    - Verhulst equation for population dynamics
    """
    
    def __init__(self, model, topography, plant_species_list: List[PlantSpecies], params):
        """
        Initialize food in this cell.
        
        Args:
            model: The model instance (required by Mesa Agent)
            topography: TopographyType (CHANNEL, FLOODED, or UNFLOODED)
            plant_species_list: List of all plant species in landscape
            params: Model parameters
        """
        super().__init__(model)
        self.topography = topography
        self.params = params
        
        # Initialize food amounts for each species
        self.food_amounts = {}  # species_id -> current food units
        self.max_food_amounts = {}  # species_id -> carrying capacity
        
        for species in plant_species_list:
            # Determine carrying capacity based on topography
            if topography.name == 'CHANNEL':
                capacity = species.plants_per_channel
            elif topography.name == 'FLOODED':
                capacity = species.plants_per_flooded
            else:  # UNFLOODED
                capacity = species.plants_per_unflooded
            
            self.max_food_amounts[species.species_id] = capacity
            
            # Start at low food availability (will grow during fruiting season)
            self.food_amounts[species.species_id] = capacity * params.initial_food_percentage
    
    def update_food(self, season: int, day_in_season: int, days_in_season: int):
        """
        Update food amounts using Verhulst equation.
        
        During fruiting season: food grows from initial to final percentage
        Outside fruiting: food decays toward zero
        
        Args:
            season: Current season (1-4)
            day_in_season: Day number within season
            days_in_season: Total days in this season
        """
        # Verhulst equation: dN/dt = r*N*(1 - N/K)
        # Where N = population, K = carrying capacity, r = growth rate
        
        for species_id, max_amount in self.max_food_amounts.items():
            current = self.food_amounts[species_id]
            
            # Check if this species fruits in current season
            # For now, assume all species fruit in all seasons
            # TODO: Use actual seasonal fruiting patterns from plant species
            is_fruiting_season = True  # Placeholder
            
            if is_fruiting_season and max_amount > 0:
                # During fruiting: grow toward maximum
                target = max_amount * self.params.final_food_percentage
                
                # Verhulst growth: dN/dt = r*N*(1 - N/K)
                # Discrete form: N(t+1) = N(t) + r*N(t)*(1 - N(t)/K)
                r = 0.1  # Intrinsic growth rate (10% per day)
                K = target  # Carrying capacity
                
                if current > 0:
                    growth = r * current * (1 - current / K)
                    new_amount = current + growth
                    self.food_amounts[species_id] = min(new_amount, target)
                else:
                    # If no current food, start with small amount
                    self.food_amounts[species_id] = max_amount * 0.01
            else:
                # Outside fruiting: decay toward minimum
                target = max_amount * self.params.initial_food_percentage
                
                # Exponential decay: N(t+1) = N(t) * decay_factor
                decay_rate = 0.05  # 5% decay per day
                decay_factor = 1 - decay_rate
                
                new_amount = current * decay_factor
                self.food_amounts[species_id] = max(new_amount, target)
    
    def get_available_food(self, species_list: List[PlantSpecies], season: int) -> List[Tuple[PlantSpecies, float]]:
        """
        Get list of available food options in this cell.
        
        Returns:
            List of (PlantSpecies, amount_available) tuples
        """
        available = []
        for species in species_list:
            if species.is_fruiting(season) and self.food_amounts.get(species.species_id, 0) > 0:
                available.append((species, self.food_amounts[species.species_id]))
        return available
    
    def consume_food(self, species_id: int, amount: float):
        """Remove consumed food from cell"""
        current = self.food_amounts.get(species_id, 0)
        self.food_amounts[species_id] = max(0, current - amount)


def load_plant_species(excel_file: str, landscape: str) -> List[PlantSpecies]:
    """
    Load all plant species from Excel file.
    
    Args:
        excel_file: Path to parameters.xls
        landscape: 'voi' or 'turkana'
        
    Returns:
        List of PlantSpecies objects
    """
    workbook = xlrd.open_workbook(excel_file)
    sheet_name = f'{landscape} plant parameters'
    sheet = workbook.sheet_by_name(sheet_name)
    
    # Row 1 contains column headers
    headers = []
    for col in range(sheet.ncols):
        header = str(sheet.cell_value(1, col)).strip()
        headers.append(header)
    
    # Load plant species starting from row 2
    plant_species = []
    
    for row in range(2, sheet.nrows):
        name = sheet.cell_value(row, 0)
        if not name or not str(name).strip():
            continue
        
        # Build parameter dictionary
        params = {}
        for col, header in enumerate(headers):
            if header:
                try:
                    value = sheet.cell_value(row, col)
                    params[header] = value
                except:
                    params[header] = None
        
        # Get species ID
        species_id = int(params.get('id number', row - 1))
        
        # Simplified seasonal fruiting for now
        # TODO: Load actual fruiting patterns from Excel
        params['seasons_fruiting'] = [True, True, True, True]  # Fruits all seasons
        
        # Default values if not in Excel
        params.setdefault('grams_per_feeding_unit', 100.0)
        params.setdefault('calories_per_gram', 2.0)
        params.setdefault('visibility_probability', 0.7)
        params.setdefault('handling_time_minutes', 5.0)
        
        species = PlantSpecies(species_id, str(name), params)
        plant_species.append(species)
    
    print(f"  Loaded {len(plant_species)} plant species")
    return plant_species


if __name__ == "__main__":
    # Test plant loading
    print("Testing plant species loading...")
    species_list = load_plant_species('parameters.xls', 'voi')
    
    print(f"\nLoaded {len(species_list)} species")
    print("\nFirst 5 species:")
    for sp in species_list[:5]:
        print(f"  {sp}")
    
    print("\nTop 5 by return rate:")
    sorted_species = sorted(species_list, key=lambda s: s.return_rate, reverse=True)
    for sp in sorted_species[:5]:
        print(f"  {sp}")
