import random

class Grid3D:
    def __init__(self, size):
        self.size = size # (x, y, z)
        self.obstacles = set()
    
    def generate_random_obstacles(self, num_obstacles, start, goal):
        self.obstacles.clear()
        count = 0
        while count < num_obstacles:
            x = random.randint(0, self.size[0] - 1)
            y = random.randint(0, self.size[1] - 1)
            z = random.randint(0, self.size[2] - 1)
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
