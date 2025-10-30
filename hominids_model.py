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
        super().__init__(model)
        self.unique_id = unique_id  # Set unique_id manually for Mesa 3.x

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

        # Detailed calorie tracking (from Agent.java:148-164)
        n_seasons = self.model.params.number_of_seasons
        n_days = self.model.params.days_in_year

        # Calorie tracking by season
        self.plant_calories_by_season = [0.0] * n_seasons
        self.carcass_calories_by_season = [0.0] * n_seasons
        self.root_calories_by_season = [0.0] * n_seasons  # Dug plants (tubers)
        self.nonroot_calories_by_season = [0.0] * n_seasons  # Non-dug plants

        # Calorie tracking by day
        self.daily_plant_calories = [0.0] * n_days
        self.daily_carcass_calories = [0.0] * n_days

        # Carcass management
        self.ignored_carcasses = []  # Carcasses agent has abandoned
        self.wait_timer = 0  # Minutes remaining to wait at carcass
        self.waiting_at_carcass = None  # Carcass agent is waiting at

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
        
        # Get food options in neighborhood (9-cell Moore neighborhood)
        food_options = self.scan_for_food()

        # Check for carcasses if agent can eat meat
        carcass_options = self.scan_for_carcasses()

        # Check for carcass calls from other agents
        called_carcass = self.check_for_carcass_calls()
        if called_carcass and called_carcass not in carcass_options:
            carcass_options.append(called_carcass)

        # Choose between plant food and carcass meat (optimal foraging)
        best_plant, plant_cell = self.choose_best_food(food_options) if food_options else (None, None)
        best_carcass = self.choose_best_carcass(carcass_options) if carcass_options else None

        # Choose the option with highest return rate
        if best_plant and best_carcass:
            # Compare return rates (meat has higher calories per gram)
            plant_return = best_plant.return_rate
            meat_return = (self.model.params.carcass_calories_per_gram *
                          self.model.params.carcass_grams_eaten_per_unit_time)

            if meat_return > plant_return:
                self.scavenge_carcass(best_carcass)
            else:
                # Move to plant cell if not already there
                if plant_cell != self.pos:
                    self.model.grid.move_agent(self, plant_cell)
                    # Log travel
                    if plant_cell not in self.activity_log:
                        self.activity_log[plant_cell] = {'eating': 0, 'traveling': 0}
                    self.activity_log[plant_cell]['traveling'] += 1
                self.eat_food(best_plant)
        elif best_plant:
            # Move to plant cell if not already there
            if plant_cell != self.pos:
                self.model.grid.move_agent(self, plant_cell)
                # Log travel
                if plant_cell not in self.activity_log:
                    self.activity_log[plant_cell] = {'eating': 0, 'traveling': 0}
                self.activity_log[plant_cell]['traveling'] += 1
            self.eat_food(best_plant)
        elif best_carcass:
            self.scavenge_carcass(best_carcass)
        else:
            # No food in neighborhood, try to move
            self.move_toward_food()
        
        # Decrement active time
        self.active_time_remaining -= 1
    
    def scan_for_food(self):
        """
        Scan current cell AND neighbors for available food options.
        Returns list of (PlantSpecies, amount, cell_pos, distance) tuples.

        From Agent.java:973-1102 (plantScan method)
        Scans 9-cell Moore neighborhood including current cell.
        """
        if not hasattr(self, 'pos') or self.pos is None:
            return []

        # Get Moore neighborhood (including current cell)
        neighbors = self.model.grid.get_neighborhood(
            self.pos,
            moore=True,
            include_center=True
        )

        visible_foods = []

        for cell_pos in neighbors:
            # Get cell food
            cell_contents = self.model.grid.get_cell_list_contents([cell_pos])
            cell_food = None
            for obj in cell_contents:
                if isinstance(obj, CellFood):
                    cell_food = obj
                    break

            if not cell_food:
                continue

            # Get available foods in current season
            available_foods = cell_food.get_available_food(
                self.model.plant_species,
                self.model.current_season
            )

            # Filter by what this agent can eat and detect
            for species, amount in available_foods:
                # Check if agent can eat this
                if not species.can_be_eaten_by(
                    self.species.value,
                    self.can_dig
                ):
                    continue

                # Probabilistic detection
                if self.model.random.random() < species.visibility_probability:
                    # Calculate distance for prioritization
                    distance = self.calculate_distance(self.pos, cell_pos)
                    visible_foods.append((species, amount, cell_pos, distance))

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
        Scavenge meat from a carcass. May need to wait for others.
        """
        from carcass_system import CarcassSize

        # Count agents at carcass location
        n_agents_here = len([
            a for a in self.model.hominid_agents
            if a.pos == carcass.location and a.species == self.species
        ])

        # If first to arrive and cooperator, notify others
        if n_agents_here == 1 and self.cooperates:
            self.notify_others_of_carcass(carcass)

        # Check if can eat (small carcass or enough cooperators)
        required = int(self.model.params.number_of_agents_for_carcass)

        if carcass.size == CarcassSize.SMALL:
            # Small carcass - can eat alone
            self._consume_meat(carcass)
        elif n_agents_here >= required:
            # Enough cooperators present
            self._consume_meat(carcass)
        elif self.cooperates and self.wait_timer == 0:
            # Start waiting for help
            self.wait_timer = 10  # Wait 10 minutes (configurable)
            self.waiting_at_carcass = carcass
        elif self.cooperates and self.waiting_at_carcass == carcass:
            # Continue waiting
            can_eat = self.wait_at_carcass(carcass)
            if can_eat:
                self._consume_meat(carcass)
        else:
            # Non-cooperator can't handle large carcass
            self.ignore_carcass(carcass)

    def notify_others_of_carcass(self, carcass):
        """
        Cooperators call others to carcasses within earshot.

        From Agent.java:1847-1849
        """
        if not self.cooperates:
            return

        # Add to shared found carcasses list
        if carcass not in self.model.found_carcasses:
            self.model.found_carcasses.append(carcass)

        # Could add logging here for debugging
        # print(f"Agent {self.unique_id} called others to carcass at {carcass.location}")

    def check_for_carcass_calls(self):
        """
        Check if other agents have called about carcasses within earshot.

        From Agent.java:1266-1394

        Returns:
            Carcass object if one is found within earshot, None otherwise
        """
        if not self.can_eat_meat:
            return None

        if not self.model.found_carcasses:
            return None

        # Get earshot distance from parameters (default 10 cells)
        earshot = int(self.model.params.earshot_distance)

        # Find closest carcass within earshot
        closest_carcass = None
        closest_distance = earshot + 1  # Start beyond earshot

        for carcass in self.model.found_carcasses:
            # Skip if already ignored
            if hasattr(self, 'ignored_carcasses') and carcass in self.ignored_carcasses:
                continue

            # Calculate Manhattan distance (faster than Euclidean)
            dx = abs(carcass.location[0] - self.pos[0])
            dy = abs(carcass.location[1] - self.pos[1])

            # Account for toroidal wrapping
            if dx > self.model.grid.width / 2:
                dx = self.model.grid.width - dx
            if dy > self.model.grid.height / 2:
                dy = self.model.grid.height - dy

            distance = dx + dy  # Manhattan distance

            if distance <= earshot and distance < closest_distance:
                closest_distance = distance
                closest_carcass = carcass

        return closest_carcass

    def ignore_carcass(self, carcass):
        """Add carcass to ignore list for this day."""
        if carcass not in self.ignored_carcasses:
            self.ignored_carcasses.append(carcass)

    def is_carcass_ignored(self, carcass):
        """Check if carcass is being ignored."""
        return carcass in self.ignored_carcasses

    def wait_at_carcass(self, carcass):
        """
        Wait for other agents to arrive at medium/large carcass.

        From Agent.java:685-719
        """
        # Count how many agents of same species are at carcass
        n_agents_present = len([
            a for a in self.model.hominid_agents
            if a.pos == carcass.location and a.species == self.species
        ])

        # Get required number from parameters
        required = int(self.model.params.number_of_agents_for_carcass)

        if n_agents_present >= required:
            # Enough agents arrived, start eating
            self.wait_timer = 0
            self.waiting_at_carcass = None
            return True  # Ready to eat

        # Check if wait timer expired
        if self.wait_timer <= 0:
            # Give up on this carcass
            self.ignore_carcass(carcass)
            self.waiting_at_carcass = None
            return False  # Gave up

        # Continue waiting
        self.wait_timer -= 1
        return False  # Still waiting

    def _consume_meat(self, carcass):
        """
        Actually consume meat from carcass.
        Extracted from scavenge_carcass for cleaner logic.
        """
        from carcass_system import calculate_meat_consumption

        # Calculate how much meat to consume
        meat_grams = calculate_meat_consumption(carcass, self, self.model.params)
        actual_consumed = min(
            meat_grams,
            self.belly_capacity_grams - self.gut_contents_grams
        )

        if actual_consumed <= 0:
            return

        # Remove from carcass
        carcass.consume_meat(actual_consumed)

        # Calculate calories
        calories_gained = actual_consumed * self.model.params.carcass_calories_per_gram

        # Update agent state
        self.calories_today += calories_gained
        self.gut_contents_grams += actual_consumed

        # Track by season and day
        season_idx = self.model.current_season - 1
        day_idx = self.model.current_day - 1

        self.carcass_calories_by_season[season_idx] += calories_gained
        self.daily_carcass_calories[day_idx] += calories_gained

        # Log activity
        if self.pos not in self.activity_log:
            self.activity_log[self.pos] = {'eating': 0, 'traveling': 0}
        self.activity_log[self.pos]['eating'] += 1

    def choose_best_food(self, food_options):
        """
        Apply optimal foraging: choose food with highest return rate.
        If ties, choose closest. If still tied, random.

        From Agent.java:973-1102 (plantScan prioritization)

        Args:
            food_options: List of (PlantSpecies, amount, cell_pos, distance) tuples

        Returns:
            Tuple of (PlantSpecies, cell_pos) or (None, None)
        """
        if not food_options:
            return None, None

        # Filter out foods we can't eat due to gut capacity
        viable_options = []
        for species, amount, cell_pos, distance in food_options:
            if amount > 0 and self.gut_contents_grams < self.belly_capacity_grams:
                viable_options.append((species, cell_pos, distance))

        if not viable_options:
            return None, None

        # Sort by: 1) return rate (descending), 2) distance (ascending)
        # This gives us highest caloric value first, then closest
        viable_options.sort(key=lambda x: (-x[0].return_rate, x[2]))

        # Get all options with best return rate and distance
        best_rate = viable_options[0][0].return_rate
        best_distance = viable_options[0][2]

        best_foods = [(sp, pos) for sp, pos, dist in viable_options
                      if sp.return_rate == best_rate and dist == best_distance]

        # Random tiebreaker
        if best_foods:
            return self.random.choice(best_foods)

        return None, None
    
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

        # Track by season and day
        season_idx = self.model.current_season - 1  # Seasons are 1-indexed
        day_idx = self.model.current_day - 1  # Days are 1-indexed

        # Track plant calories
        self.plant_calories_by_season[season_idx] += calories_gained
        self.daily_plant_calories[day_idx] += calories_gained

        # Track root vs non-root
        # Roots are plants with tools_required or has_digging_phase
        if plant_species.tools_required or plant_species.has_digging_phase:
            self.root_calories_by_season[season_idx] += calories_gained
        else:
            self.nonroot_calories_by_season[season_idx] += calories_gained

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

    def calculate_distance(self, pos1, pos2):
        """
        Calculate Euclidean distance between two positions.
        Accounts for toroidal wrapping.

        Args:
            pos1: First position (x, y)
            pos2: Second position (x, y)

        Returns:
            float: Euclidean distance
        """
        x1, y1 = pos1
        x2, y2 = pos2

        # Account for toroidal wrapping
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)

        # Check if wrapping is shorter
        if dx > self.model.grid.width / 2:
            dx = self.model.grid.width - dx
        if dy > self.model.grid.height / 2:
            dy = self.model.grid.height - dy

        return (dx**2 + dy**2)**0.5

    def evaluate_cell_prospects(self, cell_pos):
        """
        Evaluate food prospects in a given cell.

        From Agent.java:973-1102 (plantScan and bestVisibleCrop)

        Args:
            cell_pos: Grid position (x, y) to evaluate

        Returns:
            float: Estimated caloric value available in cell
        """
        cell_contents = self.model.grid.get_cell_list_contents([cell_pos])

        # Find CellFood object
        cell_food = None
        for obj in cell_contents:
            if isinstance(obj, CellFood):
                cell_food = obj
                break

        if not cell_food:
            return 0.0

        # Get available foods
        available_foods = cell_food.get_available_food(
            self.model.plant_species,
            self.model.current_season
        )

        # Calculate total caloric value considering visibility
        total_value = 0.0
        for species, amount in available_foods:
            if species.can_be_eaten_by(self.species.value, self.can_dig):
                # Expected value = return rate (calories per minute)
                # Higher return rate = more valuable food
                total_value += species.return_rate * species.visibility_probability

        return total_value

    def move_toward_food(self):
        """
        Intelligent movement: scan neighbors, evaluate prospects, move to best.

        Algorithm from Agent.java:973-1102:
        1. Scan all 8 neighbors + current cell (9 cells total)
        2. Evaluate food prospects in each
        3. For cells with food, prioritize by:
           a) Highest caloric value (return rate)
           b) Closest distance (tiebreaker)
        4. If no food in neighborhood, wander to distant cell
        """
        if not hasattr(self, 'pos') or self.pos is None:
            return

        # Get Moore neighborhood (8 neighbors + current cell)
        neighbors = self.model.grid.get_neighborhood(
            self.pos,
            moore=True,
            include_center=True
        )

        # Evaluate each cell
        cell_evaluations = []
        for cell_pos in neighbors:
            caloric_value = self.evaluate_cell_prospects(cell_pos)
            distance = self.calculate_distance(self.pos, cell_pos)

            # Classify by distance for original's orientation categories
            if distance < 0.01:
                orientation = 'same'
            elif distance < 1.01:
                orientation = 'adjacent'
            else:
                orientation = 'corner'

            cell_evaluations.append({
                'pos': cell_pos,
                'value': caloric_value,
                'distance': distance,
                'orientation': orientation
            })

        # Find best cells (highest value, then closest)
        best_cells = []
        best_value = 0.0
        best_distance = float('inf')

        for cell in cell_evaluations:
            if cell['value'] > best_value:
                # Found better food
                best_cells = [cell]
                best_value = cell['value']
                best_distance = cell['distance']
            elif cell['value'] == best_value and cell['value'] > 0:
                # Same value, check distance
                if cell['distance'] < best_distance:
                    best_cells = [cell]
                    best_distance = cell['distance']
                elif cell['distance'] == best_distance:
                    best_cells.append(cell)

        if best_cells and best_value > 0:
            # Move to one of the best cells (random tiebreaker)
            chosen = self.random.choice(best_cells)
            if chosen['pos'] != self.pos:
                self.model.grid.move_agent(self, chosen['pos'])

                # Log travel
                if chosen['pos'] not in self.activity_log:
                    self.activity_log[chosen['pos']] = {'eating': 0, 'traveling': 0}
                self.activity_log[chosen['pos']]['traveling'] += 1
        else:
            # No food in neighborhood - wander toward distant cell
            self._wander_to_distant_cell()

    def _wander_to_distant_cell(self):
        """
        When no food in neighborhood, wander toward distant cell.
        Uses wandering_distance parameter from original model.

        From Agent.java:1040-1050
        """
        # Get cells at wandering distance (default 2 cells away)
        wander_dist = int(self.model.params.wandering_distance)

        # Get cells at approximately wandering_distance away
        distant_cells = []
        for dx in range(-wander_dist, wander_dist + 1):
            for dy in range(-wander_dist, wander_dist + 1):
                # Skip cells too close
                if abs(dx) < wander_dist and abs(dy) < wander_dist:
                    continue

                new_x = (self.pos[0] + dx) % self.model.grid.width
                new_y = (self.pos[1] + dy) % self.model.grid.height
                distant_cells.append((new_x, new_y))

        if distant_cells:
            target = self.random.choice(distant_cells)

            # Move one step toward target (diagonal-first)
            dx = target[0] - self.pos[0]
            dy = target[1] - self.pos[1]

            # Account for toroidal wrapping - go the shorter way
            if abs(dx) > self.model.grid.width / 2:
                dx = -int(dx / abs(dx)) * (self.model.grid.width - abs(dx))
            if abs(dy) > self.model.grid.height / 2:
                dy = -int(dy / abs(dy)) * (self.model.grid.height - abs(dy))

            # Determine move direction (diagonal first, then cardinal)
            step_x = 0 if dx == 0 else (1 if dx > 0 else -1)
            step_y = 0 if dy == 0 else (1 if dy > 0 else -1)

            new_pos = (
                (self.pos[0] + step_x) % self.model.grid.width,
                (self.pos[1] + step_y) % self.model.grid.height
            )

            self.model.grid.move_agent(self, new_pos)

            # Log wandering
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

        # Shared found carcasses list for agent communication
        self.found_carcasses = []  # Carcasses discovered this timestep

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
        # Clear found carcasses list each timestep
        self.found_carcasses = []

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
            # Reset ignored carcasses each day
            agent.ignored_carcasses = []
            agent.wait_timer = 0
            agent.waiting_at_carcass = None
        
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
