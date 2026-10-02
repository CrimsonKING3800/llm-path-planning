import random

class Grid3D:
    def __init__(self, size):
        self.size = size # (x, y, z)
        self.obstacles = set()
    
    def generate_random_obstacles(self, num_obstacles, start, goal, rand_instance=None):
        if num_obstacles < 0:
            raise ValueError(f"Number of obstacles cannot be negative, got {num_obstacles}")
            
        total_cells = self.size[0] * self.size[1] * self.size[2]
        max_obstacles = total_cells - 2 # excluding start and goal
        if num_obstacles > max_obstacles:
            raise ValueError(f"Requested {num_obstacles} obstacles, but only {max_obstacles} cells are available.")
            
        rng = rand_instance if rand_instance is not None else random.Random()
        
        self.obstacles.clear()
        count = 0
        while count < num_obstacles:
            x = rng.randint(0, self.size[0] - 1)
            y = rng.randint(0, self.size[1] - 1)
            z = rng.randint(0, self.size[2] - 1)
            obs = (x, y, z)
            if obs != start and obs != goal and obs not in self.obstacles:
                self.obstacles.add(obs)
                count += 1
    
    def is_valid(self, point):
        x, y, z = point
        return (0 <= x < self.size[0] and 
                0 <= y < self.size[1] and 
                0 <= z < self.size[2])
    
    def is_obstacle(self, point):
        return point in self.obstacles
    
    def get_neighbors_3d(self, point):
        x, y, z = point
        # 26-connected movement (all adjacent cells in 3D)
        # Diagonal collision rule: Unrestricted diagonal movement.
        # A diagonal move is permitted as long as the destination cell is within bounds and not an obstacle.
        # It does not check if the intermediate/adjacent orthogonal cells are free.
        neighbors = []
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                for dz in [-1, 0, 1]:
                    if dx == 0 and dy == 0 and dz == 0:
                        continue
                    n = (x + dx, y + dy, z + dz)
                    if self.is_valid(n) and not self.is_obstacle(n):
                        neighbors.append(n)
        return neighbors

    def are_neighbors(self, p1, p2):
        """Check if p2 is a valid neighbor of p1 according to movement rules."""
        if not self.is_valid(p1) or not self.is_valid(p2):
            return False
        if self.is_obstacle(p1) or self.is_obstacle(p2):
            return False
        dx = abs(p1[0] - p2[0])
        dy = abs(p1[1] - p2[1])
        dz = abs(p1[2] - p2[2])
        if dx <= 1 and dy <= 1 and dz <= 1 and (dx + dy + dz > 0):
            return True
        return False
