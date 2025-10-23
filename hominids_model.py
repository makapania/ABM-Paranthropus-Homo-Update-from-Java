"""
HOMINIDS Agent-Based Model - Python Implementation
Based on Griffith et al. (2010)

This model simulates early Pleistocene hominid foraging behavior using
optimal foraging theory. It includes two species (Homo ergaster and 
Australopithecus boisei) foraging in East African landscapes.

Author: Python conversion from original Java implementation
Date: 2025
"""

import numpy as np
import pandas as pd
from mesa import Agent, Model
from mesa.space import MultiGrid
from mesa.datacollection import DataCollector
import json
import xlrd
from enum import Enum
from typing import List, Tuple, Optional
import random

# Import plant system
from plant_system import PlantSpecies, CellFood, load_plant_species

# Import carcass system
from carcass_system import CarcassManager, can_scavenge_carcass, calculate_meat_consumption

# Import output generator
from output_generator import generate_all_outputs


class TopographyType(Enum):
    """Cell topography types matching the original model"""
    CHANNEL = 0
    FLOODED = 1
    UNFLOODED = 2


class HominidSpecies(Enum):
    """Hominid species types"""
    BOISEI = "boisei"
    ERGASTER = "ergaster"


class Parameters:
    """
    Central parameter storage matching the Excel parameter file.
    
    This class loads and stores all simulation parameters from the Excel file,
    making them easily accessible throughout the model.
    """
    
    def __init__(self, excel_file: str, landscape: str):
        """
        Load parameters from Excel file.
        
        Args:
            excel_file: Path to parameters.xls file
            landscape: Either 'voi' or 'turkana'
        """
        workbook = xlrd.open_workbook(excel_file)
        
        # Load general parameters
        self._load_general_parameters(workbook)
        
        # Load landscape-specific parameters
        self._load_landscape_parameters(workbook, landscape)
        
        # Load plant parameters
        self._load_plant_parameters(workbook, landscape)
        
        print(f"Loaded parameters for {landscape} landscape")
    
    def _load_general_parameters(self, workbook):
        """Load general simulation parameters"""
        sheet = workbook.sheet_by_name('general parameters')
        
        # Movement and sensing
        self.wandering_distance = 2.0
        self.earshot_distance = 10.0
        self.nest_scan_distance = 10.0
        
        # Temporal structure
        self.first_day = 1
        self.days_in_year = 365
        self.number_of_seasons = 4
        self.active_time_units_per_day = 720  # 12 hours * 60 minutes
        self.minutes_per_time_unit = 1
        self.extra_nesting_steps = 180  # Extra time for nesting
        
        # Plant growth parameters
        self.initial_food_percentage = 0.01
        self.final_food_percentage = 0.99
        self.plant_variance = 0.0
        
        # Boisei parameters
        self.boisei_daily_calorie_requirement = 2500.0
        self.boisei_belly_capacity_grams = 4500.0
        self.boisei_diet_track_length = 14  # Days to track
        self.boisei_diet_threshold = 0.5  # Fraction of daily calories
        self.boisei_group_nesting_calorie_threshold = 0.75
        self.boisei_group_nesting_agent_threshold = 0.25
        
        # Ergaster parameters
        self.ergaster_daily_calorie_requirement = 3500.0
        self.ergaster_belly_capacity_grams = 5000.0
        self.ergaster_diet_track_length = 14
        self.ergaster_diet_threshold = 0.5
        self.ergaster_group_nesting_calorie_threshold = 0.75
        self.ergaster_group_nesting_agent_threshold = 0.25
        
        # Carcass parameters
        self.number_of_agents_for_carcass = 3
        self.carcass_detection_range = 5.0
        self.carcass_grams_eaten_per_unit_time = 50.0
        self.carcass_calories_per_gram = 1570.0
        self.single_carcass_portion_grams = 100.0
        self.small_carcass_weight_grams = 1000.0
        self.medium_carcass_weight_grams = 10000.0
        self.large_carcass_weight_grams = 100000.0
        
        # Carcass appearance probabilities by zone
        self.channel_new_carcass_prob = 0.000456621
        self.flooded_new_carcass_prob = 0.000194825
        self.unflooded_new_carcass_prob = 0.0002739726
        
        # Carcass size distribution by zone
        self.small_carcass_in_channel_prob = 0.333
        self.medium_carcass_in_channel_prob = 0.267
        self.small_carcass_in_flooded_prob = 0.125
        self.medium_carcass_in_flooded_prob = 0.625
        self.small_carcass_in_unflooded_prob = 0.091
        self.medium_carcass_in_unflooded_prob = 0.818
    
    def _load_landscape_parameters(self, workbook, landscape):
        """Load landscape grid from Excel"""
        sheet_name = f'{landscape} landscape parameters'
        sheet = workbook.sheet_by_name(sheet_name)
        
        # Read the grid - each cell is marked as C (channel), F (flooded), or U (unflooded)
        self.grid_height = sheet.nrows
        self.grid_width = sheet.ncols
        self.landscape_grid = []
        
        for row in range(sheet.nrows):
            grid_row = []
            for col in range(sheet.ncols):
                cell_value = sheet.cell_value(row, col)
                if isinstance(cell_value, str):
                    cell_value = cell_value.upper()
                    if cell_value == 'C':
                        grid_row.append(TopographyType.CHANNEL)
                    elif cell_value == 'F':
                        grid_row.append(TopographyType.FLOODED)
                    elif cell_value == 'U':
                        grid_row.append(TopographyType.UNFLOODED)
                    else:
                        grid_row.append(TopographyType.UNFLOODED)  # Default
                else:
                    grid_row.append(TopographyType.UNFLOODED)
            self.landscape_grid.append(grid_row)
        
        print(f"  Landscape grid: {self.grid_height} x {self.grid_width} cells")
    
    def _load_plant_parameters(self, workbook, landscape):
        """Load plant species parameters using plant_system module"""
        # This will be loaded properly when model initializes
        self.plant_species = []  # Will be populated by load_plant_species()
        print(f"  Plant species: (will be loaded by model)")


class HominidAgent(Agent):
    """
    Base class for hominid agents (Boisei and Ergaster).
    
    Each agent represents an individual hominid that:
    - Forages for plant foods and/or scavenges meat
    - Makes optimal foraging decisions based on return rates
    - Nests at night (individually or in groups)
    - Tracks caloric intake and starvation risk
    - Can use tools (digging sticks) if enabled
    """
    
    def __init__(self, unique_id, model, species: HominidSpecies, 
                 group_nesting: bool = False, can_dig: bool = False,
                 can_eat_meat: bool = False, cooperates: bool = False):
        """
        Initialize a hominid agent.
        
        Args:
            unique_id: Unique identifier for this agent
            model: The HOMINIDSModel instance
            species: BOISEI or ERGASTER
            group_nesting: If True, nests with others; if False, nests individually
            can_dig: If True, can access tubers with digging sticks
            can_eat_meat: If True, can scavenge carcasses
            cooperates: If True, cooperates with others for large carcasses (requires can_eat_meat)
        """
        super().__init__(unique_id, model)
        
        self.species = species
        self.group_nesting = group_nesting
        self.can_dig = can_dig
        self.can_eat_meat = can_eat_meat
        self.cooperates = cooperates and can_eat_meat
        
        # Get species-specific parameters
        params = model.params
        if species == HominidSpecies.BOISEI:
            self.daily_calorie_requirement = params.boisei_daily_calorie_requirement
            self.belly_capacity_grams = params.boisei_belly_capacity_grams
            self.diet_track_length = int(params.boisei_diet_track_length)
            self.diet_threshold = params.boisei_diet_threshold
        else:  # ERGASTER
            self.daily_calorie_requirement = params.ergaster_daily_calorie_requirement
            self.belly_capacity_grams = params.ergaster_belly_capacity_grams
            self.diet_track_length = int(params.ergaster_diet_track_length)
            self.diet_threshold = params.ergaster_diet_threshold
        
        # State variables
        self.calories_today = 0.0
        self.calories_history = []  # Track last N days for starvation detection
        self.gut_contents_grams = 0.0
        self.active_time_remaining = params.active_time_units_per_day
        self.is_nesting = False
        self.nest_location = None
        
        # Activity tracking for output
        self.activity_log = {}  # Will track time spent in each cell
        
    def step(self):
        """
        Execute one time step (1 minute) of agent behavior.
        
        Agent behavior follows this sequence:
        1. Check if nesting time (night)
        2. If active, scan for food in current cell
        3. Choose best food option (highest return rate)
        4. Eat or move toward better food
        5. Update calorie and gut contents
        """
        if self.active_time_remaining <= 0:
            # Agent is resting/nesting
            return
        
        # Check if it's nesting time
        if self.is_nesting_time() and not self.is_nesting:
            nest_site = self.find_nest_site()
            if nest_site:
                # Move to nest site
                self.model.grid.move_agent(self, nest_site)
                self.is_nesting = True
                self.nest_location = nest_site
                return
        
        # Get food options in current cell
        food_options = self.scan_for_food()
        
        # Check for carcasses if agent can eat meat
        carcass_options = self.scan_for_carcasses()
        
        # Choose between plant food and carcass meat (optimal foraging)
        best_plant = self.choose_best_food(food_options) if food_options else None
        best_carcass = self.choose_best_carcass(carcass_options) if carcass_options else None
        
        # Choose the option with highest return rate
        if best_plant and best_carcass:
            # Compare return rates (meat has higher calories per gram)
            plant_return = best_plant.return_rate
            meat_return = (self.model.params.carcass_calories_per_gram * 
                          self.model.params.carcass_grams_eaten_per_unit_time / 
                          self.model.params.carcass_grams_eaten_per_unit_time)  # Simplified
            
            if meat_return > plant_return:
                self.scavenge_carcass(best_carcass)
            else:
                self.eat_food(best_plant)
        elif best_plant:
            self.eat_food(best_plant)
        elif best_carcass:
            self.scavenge_carcass(best_carcass)
        else:
            # No food here, try to move
            self.move_toward_food()
        
        # Decrement active time
        self.active_time_remaining -= 1
    
    def scan_for_food(self):
        """
        Scan current cell for available food options.
        Returns list of (PlantSpecies, amount) tuples for visible food.
        """
        if not hasattr(self, 'pos') or self.pos is None:
            return []
        
        # Get cell food from model
        cell_contents = self.model.grid.get_cell_list_contents([self.pos])
        
        # Find CellFood object
        cell_food = None
        for obj in cell_contents:
            if isinstance(obj, CellFood):
                cell_food = obj
                break
        
        if not cell_food:
            return []
        
        # Get available foods in current season
        available_foods = cell_food.get_available_food(
            self.model.plant_species,
            self.model.current_season
        )
        
        # Filter by what this agent can eat and detect
        visible_foods = []
        for species, amount in available_foods:
            # Check if agent can eat this
            if not species.can_be_eaten_by(
                self.species.value,
                self.can_dig
            ):
                continue
            
            # Probabilistic detection
            if self.model.random.random() < species.visibility_probability:
                visible_foods.append((species, amount))
        
        return visible_foods
    
    def scan_for_carcasses(self):
        """
        Scan for carcasses in detection range.
        Returns list of carcasses that can be scavenged.
        """
        if not hasattr(self, 'pos') or self.pos is None or not self.can_eat_meat:
            return []
        
        # Get carcasses within detection range
        nearby_carcasses = self.model.carcass_manager.get_carcasses_in_range(
            self.pos,
            self.model.params.carcass_detection_range
        )
        
        # Filter carcasses that can be scavenged
        scavengable_carcasses = []
        for carcass in nearby_carcasses:
            if can_scavenge_carcass(carcass, self, self.model.params):
                scavengable_carcasses.append(carcass)
        
        return scavengable_carcasses
    
    def choose_best_carcass(self, carcass_options):
        """
        Choose the best carcass to scavenge based on meat availability.
        
        Args:
            carcass_options: List of carcasses that can be scavenged
            
        Returns:
            Best carcass to scavenge, or None
        """
        if not carcass_options:
            return None
        
        # Choose carcass with most meat available
        best_carcass = max(carcass_options, key=lambda c: c.get_meat_available())
        return best_carcass
    
    def scavenge_carcass(self, carcass):
        """
        Scavenge meat from a carcass.
        Updates calories and gut contents.
        """
        # Calculate how much meat to consume
        meat_grams = calculate_meat_consumption(carcass, self, self.model.params)
        
        if meat_grams <= 0:
            return
        
        # Check gut capacity
        if self.gut_contents_grams + meat_grams > self.belly_capacity_grams:
            meat_grams = self.belly_capacity_grams - self.gut_contents_grams
        
        if meat_grams <= 0:
            return
        
        # Consume meat from carcass
        actual_consumed = carcass.consume_meat(meat_grams)
        
        # Calculate calories gained
        calories_gained = actual_consumed * self.model.params.carcass_calories_per_gram
        
        # Update agent state
        self.calories_today += calories_gained
        self.gut_contents_grams += actual_consumed
        
        # Log activity (for output generation)
        if self.pos not in self.activity_log:
            self.activity_log[self.pos] = {'eating': 0, 'traveling': 0}
        self.activity_log[self.pos]['eating'] += 1
    
    def choose_best_food(self, food_options):
        """
        Apply optimal foraging: choose food with highest return rate
        that agent can eat and has capacity for.
        
        Args:
            food_options: List of (PlantSpecies, amount) tuples
            
        Returns:
            PlantSpecies with highest return rate, or None
        """
        if not food_options:
            return None
        
        # Filter out foods we can't eat due to gut capacity
        viable_options = []
        for species, amount in food_options:
            if amount > 0 and self.gut_contents_grams < self.belly_capacity_grams:
                viable_options.append(species)
        
        if not viable_options:
            return None
        
        # Choose highest return rate (optimal foraging)
        best_food = max(viable_options, key=lambda s: s.return_rate)
        return best_food
    
    def eat_food(self, plant_species: 'PlantSpecies'):
        """
        Eat one feeding unit of the specified plant.
        Updates calories and gut contents.
        """
        # Check gut capacity
        grams_to_eat = min(
            plant_species.grams_per_feeding_unit,
            self.belly_capacity_grams - self.gut_contents_grams
        )
        
        if grams_to_eat <= 0:
            return
        
        # Calculate calories gained
        calories_gained = grams_to_eat * plant_species.calories_per_gram
        
        # Update agent state
        self.calories_today += calories_gained
        self.gut_contents_grams += grams_to_eat
        
        # Remove food from cell
        if hasattr(self, 'pos') and self.pos:
            cell_contents = self.model.grid.get_cell_list_contents([self.pos])
            for obj in cell_contents:
                if isinstance(obj, CellFood):
                    # Remove consumed amount
                    obj.consume_food(plant_species.species_id, 1.0)
                    break
        
        # Log activity (for output generation)
        if self.pos not in self.activity_log:
            self.activity_log[self.pos] = {'eating': 0, 'traveling': 0}
        self.activity_log[self.pos]['eating'] += 1
    
    def move_toward_food(self):
        """
        Move to an adjacent cell with better foraging prospects.
        Uses simple random movement for now.
        TODO: Implement diagonal-first movement algorithm from original model.
        """
        if not hasattr(self, 'pos') or self.pos is None:
            return
        
        # Get neighboring cells (including diagonals)
        neighbors = self.model.grid.get_neighborhood(
            self.pos,
            moore=True,  # Include diagonals
            include_center=False
        )
        
        if neighbors:
            # For now, move randomly
            # TODO: Evaluate food availability in each neighbor and move to best
            new_pos = self.random.choice(neighbors)
            self.model.grid.move_agent(self, new_pos)
            
            # Log travel
            if new_pos not in self.activity_log:
                self.activity_log[new_pos] = {'eating': 0, 'traveling': 0}
            self.activity_log[new_pos]['traveling'] += 1
    
    def find_nest_site(self):
        """
        Find appropriate nesting location based on nesting strategy
        (group vs individual).
        """
        if self.group_nesting:
            return self._find_group_nest_site()
        else:
            return self._find_individual_nest_site()
    
    def _find_individual_nest_site(self):
        """
        Find individual nesting site (nearest nesting tree).
        """
        # Look for nesting trees within scan distance
        best_nest = None
        best_distance = float('inf')
        
        for x in range(self.model.grid.width):
            for y in range(self.model.grid.height):
                # Calculate distance
                distance = abs(x - self.pos[0]) + abs(y - self.pos[1])
                
                if distance <= self.model.params.nest_scan_distance:
                    # Check if this cell has nesting trees
                    cell_contents = self.model.grid.get_cell_list_contents([(x, y)])
                    for obj in cell_contents:
                        if isinstance(obj, CellFood):
                            # Check if any plant species here is a nesting tree
                            for species in self.model.plant_species:
                                if (species.is_nesting_tree and 
                                    obj.food_amounts.get(species.species_id, 0) > 0):
                                    if distance < best_distance:
                                        best_distance = distance
                                        best_nest = (x, y)
                                    break
        
        return best_nest
    
    def _find_group_nest_site(self):
        """
        Find group nesting site based on other agents and calorie thresholds.
        """
        # Find where other agents of same species are located
        other_agents = [a for a in self.model.hominid_agents 
                        if a.species == self.species and a.unique_id != self.unique_id]
        
        if not other_agents:
            # No other agents, fall back to individual nesting
            return self._find_individual_nest_site()
        
        # Count agents in each cell
        cell_agent_counts = {}
        for agent in other_agents:
            if hasattr(agent, 'pos') and agent.pos:
                cell_agent_counts[agent.pos] = cell_agent_counts.get(agent.pos, 0) + 1
        
        # Find cells with enough agents for group nesting
        threshold = int(len(other_agents) * self.model.params.boisei_group_nesting_agent_threshold)
        suitable_cells = [pos for pos, count in cell_agent_counts.items() 
                         if count >= threshold]
        
        if suitable_cells:
            # Choose nearest suitable cell
            best_cell = None
            best_distance = float('inf')
            for cell_pos in suitable_cells:
                distance = abs(cell_pos[0] - self.pos[0]) + abs(cell_pos[1] - self.pos[1])
                if distance < best_distance:
                    best_distance = distance
                    best_cell = cell_pos
            return best_cell
        
        # No suitable group sites, fall back to individual nesting
        return self._find_individual_nest_site()
    
    def is_nesting_time(self):
        """Check if it's time to nest (end of day)"""
        return self.active_time_remaining <= self.model.params.extra_nesting_steps
    
    def check_starvation(self):
        """
        Check if agent is starving based on recent calorie history.
        Starvation = N consecutive days below threshold % of daily needs.
        """
        if len(self.calories_history) < self.diet_track_length:
            return False
        
        recent_days = self.calories_history[-self.diet_track_length:]
        threshold_calories = self.daily_calorie_requirement * self.diet_threshold
        
        starving_days = sum(1 for day_cal in recent_days if day_cal < threshold_calories)
        return starving_days >= self.diet_track_length


class HOMINIDSModel(Model):
    """
    Main HOMINIDS agent-based model.
    
    This model simulates hominid foraging in dynamic East African landscapes.
    Key features:
    - Toroidal grid (wraps at edges)
    - Seasonal plant food dynamics
    - Probabilistic carcass appearance
    - Optimal foraging decisions by agents
    - Individual and group nesting strategies
    """
    
    def __init__(self, params_file: str, landscape: str,
                 n_boisei: int, n_ergaster: int,
                 boisei_options: str = "i", ergaster_options: str = "i",
                 n_years: int = 1,
                 random_seed: Optional[int] = None):
        """
        Initialize the HOMINIDS model.
        
        Args:
            params_file: Path to parameters.xls
            landscape: 'voi' or 'turkana'
            n_boisei: Number of boisei agents
            n_ergaster: Number of ergaster agents
            boisei_options: Agent options (i/g for nesting, d for digging, M for meat, c for cooperation)
            ergaster_options: Agent options (same format)
            n_years: Number of years to simulate
            random_seed: Optional random seed for reproducibility
        """
        super().__init__()
        
        # Set random seed
        if random_seed:
            random.seed(random_seed)
            np.random.seed(random_seed)
        
        # Load parameters
        self.params = Parameters(params_file, landscape)
        self.landscape = landscape
        self.n_years = n_years
        
        # Parse agent options
        boisei_config = self._parse_agent_options(boisei_options)
        ergaster_config = self._parse_agent_options(ergaster_options)
        
        # Create grid (toroidal = wraps at edges)
        self.grid = MultiGrid(
            self.params.grid_width,
            self.params.grid_height,
            torus=True  # Toroidal wrapping
        )
        
        # Initialize agent storage
        self.hominid_agents = []
        
        # Create agents
        self._create_agents(n_boisei, HominidSpecies.BOISEI, boisei_config)
        self._create_agents(n_ergaster, HominidSpecies.ERGASTER, ergaster_config)
        
        # Initialize environment (plants, carcasses)
        self._initialize_environment()
        
        # Initialize carcass manager
        self.carcass_manager = CarcassManager(self, self.params)
        
        # Set up data collection
        self._setup_data_collection()
        
        # Simulation state
        self.current_day = 1
        self.current_season = 1
        self.current_minute = 0
        
        print(f"\n{'='*60}")
        print(f"HOMINIDS Model Initialized")
        print(f"{'='*60}")
        print(f"Landscape: {landscape}")
        print(f"Grid: {self.params.grid_height} x {self.params.grid_width} cells")
        print(f"Agents: {n_boisei} boisei, {n_ergaster} ergaster")
        print(f"Duration: {n_years} year(s)")
        print(f"{'='*60}\n")
    
    def _parse_agent_options(self, options: str) -> dict:
        """Parse agent option string (e.g., 'bid' = individual, digging)"""
        config = {
            'group_nesting': 'g' in options.lower(),
            'can_dig': 'd' in options.lower(),
            'can_eat_meat': 'm' in options.lower(),
            'cooperates': 'c' in options.lower()
        }
        return config
    
    def _create_agents(self, n_agents: int, species: HominidSpecies, config: dict):
        """Create and place agents on the grid"""
        for i in range(n_agents):
            agent = HominidAgent(
                unique_id=len(self.hominid_agents),
                model=self,
                species=species,
                **config
            )
            self.hominid_agents.append(agent)
            
            # Place agent randomly on grid
            x = self.random.randrange(self.grid.width)
            y = self.random.randrange(self.grid.height)
            self.grid.place_agent(agent, (x, y))
    
    def _initialize_environment(self):
        """Initialize plants and environmental features"""
        # Load plant species
        self.plant_species = load_plant_species(
            'parameters.xls',  # TODO: Use passed params_file
            self.landscape
        )
        
        # Create CellFood object for each grid cell
        print("Initializing food in grid cells...")
        for x in range(self.grid.width):
            for y in range(self.grid.height):
                # Get topography for this cell
                topography = self.params.landscape_grid[y][x]
                
                # Create food manager for this cell
                cell_food = CellFood(self, topography, self.plant_species, self.params)
                
                # Place on grid
                self.grid.place_agent(cell_food, (x, y))
        
        print(f"  Initialized {self.grid.width * self.grid.height} cells with food")
    
    def _setup_data_collection(self):
        """Set up data collectors for output"""
        # Helper function to safely get agent attributes
        def safe_get_attr(agent, attr, default=None):
            return getattr(agent, attr, default) if isinstance(agent, HominidAgent) else default
        
        self.datacollector = DataCollector(
            model_reporters={
                "Day": lambda m: m.current_day,
                "Season": lambda m: m.current_season,
            },
            agent_reporters={
                "Species": lambda a: a.species.value if isinstance(a, HominidAgent) else None,
                "X": lambda a: a.pos[0] if isinstance(a, HominidAgent) and hasattr(a, 'pos') and a.pos else None,
                "Y": lambda a: a.pos[1] if isinstance(a, HominidAgent) and hasattr(a, 'pos') and a.pos else None,
                "Calories": lambda a: a.calories_today if isinstance(a, HominidAgent) else None,
            }
        )
    
    def step(self):
        """
        Execute one time step (1 minute) of the simulation.
        """
        # Advance all agents in random order
        agents_shuffled = self.hominid_agents.copy()
        self.random.shuffle(agents_shuffled)
        for agent in agents_shuffled:
            agent.step()
        
        # Update plant food growth (once per day at midnight)
        if self.current_minute == 0:
            self._update_plant_food()
            # Check for new carcasses
            self.carcass_manager.check_for_new_carcasses()
            # Update carcass agent assignments
            self.carcass_manager.update_carcass_agents()
            # Remove depleted carcasses
            self.carcass_manager.remove_depleted_carcasses()
        
        # Update time
        self.current_minute += 1
        if self.current_minute >= self.params.active_time_units_per_day:
            self.current_minute = 0
            self.current_day += 1
            self._end_of_day()
        
        # Collect data
        self.datacollector.collect(self)
    
    def _update_plant_food(self):
        """Update plant food growth using Verhulst equation"""
        # Calculate day in season
        days_per_season = 365 // 4
        day_in_season = ((self.current_day - 1) % days_per_season) + 1
        
        # Update all cell food objects
        for x in range(self.grid.width):
            for y in range(self.grid.height):
                cell_contents = self.grid.get_cell_list_contents([(x, y)])
                for obj in cell_contents:
                    if isinstance(obj, CellFood):
                        obj.update_food(
                            self.current_season,
                            day_in_season,
                            days_per_season
                        )
    
    def _end_of_day(self):
        """Handle end-of-day processing"""
        # Update agent daily stats
        for agent in self.hominid_agents:
            agent.calories_history.append(agent.calories_today)
            agent.calories_today = 0.0
            agent.gut_contents_grams = 0.0
            agent.active_time_remaining = self.params.active_time_units_per_day
            # Reset nesting state for new day
            agent.is_nesting = False
            agent.nest_location = None
        
        # Check for new season
        if self.current_day > 365:
            self.current_day = 1
        
        # Update season (simplified - 4 seasons, roughly equal)
        if self.current_day <= 90:
            self.current_season = 1
        elif self.current_day <= 273:
            self.current_season = 2
        elif self.current_day <= 334:
            self.current_season = 3
        else:
            self.current_season = 4
    
    def run(self):
        """Run the complete simulation for specified years"""
        total_steps = self.n_years * 365 * self.params.active_time_units_per_day
        
        print("Starting simulation...")
        print(f"Total time steps: {total_steps:,}")
        
        for step_num in range(total_steps):
            self.step()
            
            # Progress report every simulated day
            if step_num % self.params.active_time_units_per_day == 0:
                day = step_num // self.params.active_time_units_per_day + 1
                print(f"  Day {day}/{self.n_years * 365} (Season {self.current_season})", end='\r')
        
        print("\n\nSimulation complete!")
        
        # Generate output files
        print("\nGenerating output files...")
        generate_all_outputs(self, "output")
        
        return self._get_results()
    
    def _get_results(self):
        """Get simulation results as DataFrames"""
        agent_data = self.datacollector.get_agent_vars_dataframe()
        model_data = self.datacollector.get_model_vars_dataframe()
        
        return {
            'agent_data': agent_data,
            'model_data': model_data
        }


if __name__ == "__main__":
    # This allows testing the model structure
    print("HOMINIDS Model - Python Implementation")
    print("Testing parameter loading...")
    
    params = Parameters('parameters.xls', 'voi')
    print(f"\n✓ Successfully loaded {len(params.plant_species)} plant species")
    print(f"✓ Grid dimensions: {params.grid_height} x {params.grid_width}")
