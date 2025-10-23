"""
Carcass System for HOMINIDS Model

This module implements:
1. Probabilistic carcass appearance by zone
2. Carcass sizes (small, medium, large)
3. Detection by agents
4. Individual vs cooperative scavenging
5. Meat consumption mechanics
"""

import random
from typing import List, Tuple, Optional
from enum import Enum


class CarcassSize(Enum):
    """Carcass size categories"""
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


from mesa import Agent

class Carcass(Agent):
    """
    Represents a carcass that can be scavenged by hominid agents.
    
    Carcasses have different sizes and require different numbers of agents
    to scavenge effectively. Small carcasses can be handled individually,
    while medium and large carcasses require cooperation.
    """
    
    def __init__(self, unique_id, model, size: CarcassSize, weight_grams: float, location: Tuple[int, int]):
        """
        Initialize a carcass.
        
        Args:
            unique_id: Unique identifier for this carcass
            model: The model instance
            size: Carcass size category
            weight_grams: Total weight in grams
            location: Grid position (x, y)
        """
        super().__init__(model)
        self.unique_id = unique_id
        self.size = size
        self.weight_grams = weight_grams
        self.remaining_grams = weight_grams
        self.location = location
        self.agents_present = []  # List of agent IDs currently at carcass
        
    def can_scavenge_individually(self) -> bool:
        """Check if this carcass can be scavenged by a single agent"""
        return self.size == CarcassSize.SMALL
    
    def needs_cooperation(self, n_agents_present: int, threshold: int) -> bool:
        """Check if this carcass needs multiple agents to scavenge"""
        return n_agents_present >= threshold
    
    def add_agent(self, agent_id: int):
        """Add an agent to the carcass location"""
        if agent_id not in self.agents_present:
            self.agents_present.append(agent_id)
    
    def remove_agent(self, agent_id: int):
        """Remove an agent from the carcass location"""
        if agent_id in self.agents_present:
            self.agents_present.remove(agent_id)
    
    def consume_meat(self, grams: float) -> float:
        """
        Consume meat from the carcass.
        
        Args:
            grams: Amount of meat to consume
            
        Returns:
            Actual amount consumed (may be less if carcass is depleted)
        """
        actual_consumed = min(grams, self.remaining_grams)
        self.remaining_grams -= actual_consumed
        return actual_consumed
    
    def is_depleted(self) -> bool:
        """Check if carcass is completely consumed"""
        return self.remaining_grams <= 0
    
    def get_meat_available(self) -> float:
        """Get amount of meat still available"""
        return self.remaining_grams


class CarcassManager:
    """
    Manages carcass appearance and distribution across the landscape.
    
    This class handles:
    - Probabilistic carcass appearance by topography zone
    - Carcass size distribution
    - Carcass detection by agents
    - Scavenging mechanics
    """
    
    def __init__(self, model, params):
        """
        Initialize carcass manager.
        
        Args:
            model: The HOMINIDSModel instance
            params: Model parameters
        """
        self.model = model
        self.params = params
        self.carcasses = []  # List of active carcasses
        
    def check_for_new_carcasses(self):
        """
        Check each cell for new carcass appearance based on probabilities.
        Called once per day.
        """
        for x in range(self.model.grid.width):
            for y in range(self.model.grid.height):
                # Get topography for this cell
                topography = self.params.landscape_grid[y][x]
                
                # Get appearance probability for this zone
                if topography.name == 'CHANNEL':
                    prob = self.params.channel_new_carcass_prob
                elif topography.name == 'FLOODED':
                    prob = self.params.flooded_new_carcass_prob
                else:  # UNFLOODED
                    prob = self.params.unflooded_new_carcass_prob
                
                # Check if new carcass appears
                if self.model.random.random() < prob:
                    self._create_carcass_at_location((x, y), topography)
    
    def _create_carcass_at_location(self, location: Tuple[int, int], topography):
        """
        Create a new carcass at the specified location.
        
        Args:
            location: Grid position (x, y)
            topography: TopographyType for this cell
        """
        # Determine carcass size based on zone probabilities
        size = self._determine_carcass_size(topography)
        
        # Get weight based on size
        if size == CarcassSize.SMALL:
            weight = self.params.small_carcass_weight_grams
        elif size == CarcassSize.MEDIUM:
            weight = self.params.medium_carcass_weight_grams
        else:  # LARGE
            weight = self.params.large_carcass_weight_grams
        
        # Create carcass
        carcass_id = len(self.carcasses)  # Simple ID assignment
        carcass = Carcass(carcass_id, self.model, size, weight, location)
        self.carcasses.append(carcass)
        
        # Place carcass on grid (as a special agent)
        self.model.grid.place_agent(carcass, location)
    
    def _determine_carcass_size(self, topography) -> CarcassSize:
        """
        Determine carcass size based on topography zone.
        
        Args:
            topography: TopographyType for the cell
            
        Returns:
            CarcassSize category
        """
        rand = self.model.random.random()
        
        if topography.name == 'CHANNEL':
            if rand < self.params.small_carcass_in_channel_prob:
                return CarcassSize.SMALL
            elif rand < (self.params.small_carcass_in_channel_prob + 
                        self.params.medium_carcass_in_channel_prob):
                return CarcassSize.MEDIUM
            else:
                return CarcassSize.LARGE
                
        elif topography.name == 'FLOODED':
            if rand < self.params.small_carcass_in_flooded_prob:
                return CarcassSize.SMALL
            elif rand < (self.params.small_carcass_in_flooded_prob + 
                        self.params.medium_carcass_in_flooded_prob):
                return CarcassSize.MEDIUM
            else:
                return CarcassSize.LARGE
                
        else:  # UNFLOODED
            if rand < self.params.small_carcass_in_unflooded_prob:
                return CarcassSize.SMALL
            elif rand < (self.params.small_carcass_in_unflooded_prob + 
                        self.params.medium_carcass_in_unflooded_prob):
                return CarcassSize.MEDIUM
            else:
                return CarcassSize.LARGE
    
    def get_carcasses_in_range(self, agent_pos: Tuple[int, int], 
                              detection_range: float) -> List[Carcass]:
        """
        Get all carcasses within detection range of an agent.
        
        Args:
            agent_pos: Agent's grid position (x, y)
            detection_range: Detection range in grid cells
            
        Returns:
            List of carcasses within range
        """
        nearby_carcasses = []
        
        for carcass in self.carcasses:
            if carcass.is_depleted():
                continue
                
            # Calculate distance (Manhattan distance for simplicity)
            distance = abs(agent_pos[0] - carcass.location[0]) + abs(agent_pos[1] - carcass.location[1])
            
            if distance <= detection_range:
                nearby_carcasses.append(carcass)
        
        return nearby_carcasses
    
    def update_carcass_agents(self):
        """Update which agents are present at each carcass"""
        # Clear all agent assignments
        for carcass in self.carcasses:
            carcass.agents_present.clear()
        
        # Check which agents are at carcass locations
        for agent in self.model.hominid_agents:
            if hasattr(agent, 'pos') and agent.pos:
                for carcass in self.carcasses:
                    if carcass.location == agent.pos:
                        carcass.add_agent(agent.unique_id)
    
    def remove_depleted_carcasses(self):
        """Remove carcasses that have been completely consumed"""
        self.carcasses = [c for c in self.carcasses if not c.is_depleted()]
    
    def get_carcass_at_location(self, location: Tuple[int, int]) -> Optional[Carcass]:
        """
        Get carcass at specific location, if any.
        
        Args:
            location: Grid position (x, y)
            
        Returns:
            Carcass at location, or None if no carcass
        """
        for carcass in self.carcasses:
            if carcass.location == location and not carcass.is_depleted():
                return carcass
        return None


def can_scavenge_carcass(carcass: Carcass, agent, params) -> bool:
    """
    Check if an agent can scavenge a carcass.
    
    Args:
        carcass: The carcass to check
        agent: The agent attempting to scavenge
        params: Model parameters
        
    Returns:
        True if agent can scavenge this carcass
    """
    # Check if agent can eat meat
    if not agent.can_eat_meat:
        return False
    
    # Check if carcass is depleted
    if carcass.is_depleted():
        return False
    
    # For small carcasses, individual scavenging is always possible
    if carcass.can_scavenge_individually():
        return True
    
    # For medium/large carcasses, need cooperation
    if agent.cooperates:
        n_agents_present = len(carcass.agents_present)
        return carcass.needs_cooperation(n_agents_present, params.number_of_agents_for_carcass)
    
    return False


def calculate_meat_consumption(carcass: Carcass, agent, params) -> float:
    """
    Calculate how much meat an agent can consume from a carcass.
    
    Args:
        carcass: The carcass being scavenged
        agent: The agent consuming meat
        params: Model parameters
        
    Returns:
        Grams of meat consumed
    """
    # Base consumption rate
    base_consumption = params.carcass_grams_eaten_per_unit_time
    
    # Adjust for carcass size and cooperation
    if carcass.size == CarcassSize.SMALL:
        # Individual consumption
        consumption = base_consumption
    else:
        # Cooperative consumption - divide among present agents
        n_agents = len(carcass.agents_present)
        if n_agents > 0:
            consumption = base_consumption / n_agents
        else:
            consumption = 0
    
    # Limit by carcass availability
    actual_consumption = min(consumption, carcass.get_meat_available())
    
    return actual_consumption

