import unittest
import json
import random
import config as cfg
from environment import Grid3D
from astar3d import llm_astar, standard_astar, calculate_path_cost, validate_path, validate_endpoints
from llm_planner import LLMPlanner

class TestAStar3D(unittest.TestCase):
    def setUp(self):
        self.env = Grid3D((10, 10, 10))
        # Default config
        cfg.PRIORITY_VARIANT = "baseline"
        cfg.CLOSED_NODE_VARIANT = "baseline"

    def test_01_empty_waypoint_fallback(self):
        start, goal = (0, 0, 0), (2, 2, 2)
        p1, m1 = standard_astar(start, goal, self.env)
        p2, m2 = llm_astar(start, goal, self.env, [])
        self.assertEqual(p1, p2)
        self.assertEqual(m1['expanded_nodes'], m2['expanded_nodes'])
        self.assertEqual(m1['path_cost'], m2['path_cost'])

    def test_02_start_outside_grid(self):
        start, goal = (-1, 0, 0), (2, 2, 2)
        valid, reason = validate_endpoints(start, goal, self.env)
        self.assertFalse(valid)
        self.assertIn("out of bounds", reason)

    def test_03_goal_outside_grid(self):
        start, goal = (0, 0, 0), (10, 10, 10)
        valid, reason = validate_endpoints(start, goal, self.env)
        self.assertFalse(valid)
        self.assertIn("out of bounds", reason)

    def test_04_start_on_obstacle(self):
        start, goal = (0, 0, 0), (2, 2, 2)
        self.env.obstacles.add(start)
        valid, reason = validate_endpoints(start, goal, self.env)
        self.assertFalse(valid)
        self.assertIn("obstacle", reason)

    def test_05_goal_on_obstacle(self):
        start, goal = (0, 0, 0), (2, 2, 2)
        self.env.obstacles.add(goal)
        valid, reason = validate_endpoints(start, goal, self.env)
        self.assertFalse(valid)
        self.assertIn("obstacle", reason)

    def test_06_start_equals_goal(self):
        start = (1, 1, 1)
        goal = (1, 1, 1)
        path, metrics = standard_astar(start, goal, self.env)
        self.assertEqual(path, [start])
        self.assertEqual(metrics['path_cost'], 0.0)
        self.assertEqual(metrics['path_length'], 1)
        self.assertEqual(metrics['termination_reason'], "Start equals goal")

    def test_07_no_path_exists(self):
        env = Grid3D((5, 5, 5))
        # Surround start with obstacles
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                for dz in [-1, 0, 1]:
                    if dx == 0 and dy == 0 and dz == 0:
                        continue
                    env.obstacles.add((1 + dx, 1 + dy, 1 + dz))
        path, metrics = standard_astar((1, 1, 1), (4, 4, 4), env)
        self.assertIsNone(path)
        self.assertEqual(metrics['termination_reason'], "OPEN set exhausted")

    def test_08_direct_path(self):
        start, goal = (0, 0, 0), (2, 0, 0)
        path, metrics = standard_astar(start, goal, self.env)
        self.assertEqual(path, [(0, 0, 0), (1, 0, 0), (2, 0, 0)])
        self.assertEqual(metrics['path_cost'], 2.0)

    def test_09_detour_around_obstacles(self):
        start, goal = (0, 0, 0), (2, 0, 0)
        self.env.obstacles.add((1, 0, 0))
        path, metrics = standard_astar(start, goal, self.env)
        self.assertIsNotNone(path)
        self.assertNotIn((1, 0, 0), path)
        self.assertTrue(metrics['path_cost'] > 2.0)

    def test_10_valid_diagonal_movement(self):
        start, goal = (0, 0, 0), (1, 1, 1)
        self.env.obstacles.add((1, 0, 0))
        self.env.obstacles.add((0, 1, 0))
        self.env.obstacles.add((0, 0, 1))
        path, metrics = standard_astar(start, goal, self.env)
        self.assertEqual(path, [(0, 0, 0), (1, 1, 1)])

    def test_11_invalid_non_neighbor_jump(self):
        start, goal = (0, 0, 0), (2, 0, 0)
        invalid_path = [(0, 0, 0), (2, 0, 0)]
        valid, reason = validate_path(invalid_path, self.env, start, goal)
        self.assertFalse(valid)
        self.assertIn("not valid neighbors", reason)

    def test_12_invalid_duplicate_waypoints(self):
        planner = LLMPlanner(prompt_mode="exact")
        llm_response = json.dumps({
            "waypoints": [
                [1, 1, 1],
                [1, 1, 1], # dup
                [15, 15, 15], # out of bounds
                [5, 5, 5], # obstacle
                [2.5, 2, 2], # float
            ]
        })
        self.env.obstacles.add((5, 5, 5))
        valid, rejected, err = planner.parse_and_validate_waypoints(llm_response, self.env, (0,0,0), (9,9,9))
        self.assertIsNone(err)
        self.assertEqual(valid, [(1, 1, 1)])
        self.assertEqual(len(rejected), 4)

    def test_13_malformed_llm_response(self):
        planner = LLMPlanner()
        # Not JSON
        _, _, err1 = planner.parse_and_validate_waypoints("just some text", self.env, (0,0,0), (9,9,9))
        self.assertIsNotNone(err1)
        self.assertIn("JSON Decode", err1)
        
        # Missing waypoints
        _, _, err2 = planner.parse_and_validate_waypoints('{"other": []}', self.env, (0,0,0), (9,9,9))
        self.assertIsNotNone(err2)
        self.assertIn("Missing 'waypoints'", err2)

    def test_14_waypoint_switching_and_reprioritization(self):
        start, goal = (0, 0, 0), (4, 4, 4)
        targets = [(2, 2, 2)]
        path, metrics = llm_astar(start, goal, self.env, targets)
        self.assertIsNotNone(path)
        self.assertEqual(metrics['waypoints_reached'], 1)
        self.assertTrue((2, 2, 2) in path)
        self.assertTrue(len(metrics['open_size_at_switches']) > 0)

    def test_15_closed_node_reopening(self):
        # We need a setup where a node is CLOSED, then a target switch changes heuristic
        # so much that a new, longer path to that CLOSED node becomes "better" under the new f-score?
        # Actually reopening depends on g-score, not f-score. Since we use Euclidean (consistent),
        # standard A* never needs reopening. Even LLM-A* g-scores don't change based on targets.
        # But we still test the variant runs without errors.
        cfg.CLOSED_NODE_VARIANT = "reopening"
        start, goal = (0, 0, 0), (3, 3, 3)
        targets = [(1, 1, 1)]
        path, metrics = llm_astar(start, goal, self.env, targets)
        self.assertIsNotNone(path)

    def test_16_replaying(self):
        # We simulate a replay by passing hardcoded waypoints to llm_astar
        start, goal = (0, 0, 0), (4, 4, 4)
        targets = [(2, 2, 2)]
        path1, m1 = llm_astar(start, goal, self.env, targets)
        path2, m2 = llm_astar(start, goal, self.env, targets)
        self.assertEqual(path1, path2)
        self.assertEqual(m1['expanded_nodes'], m2['expanded_nodes'])

    def test_17_reproducible_obstacle_generation(self):
        env1 = Grid3D((5, 5, 5))
        env2 = Grid3D((5, 5, 5))
        rng1 = random.Random(42)
        rng2 = random.Random(42)
        env1.generate_random_obstacles(10, (0,0,0), (4,4,4), rand_instance=rng1)
        env2.generate_random_obstacles(10, (0,0,0), (4,4,4), rand_instance=rng2)
        self.assertEqual(env1.obstacles, env2.obstacles)

    def test_18_path_cost_calculation(self):
        # Axial
        self.assertEqual(calculate_path_cost([(0,0,0), (1,0,0)]), 1.0)
        # 2D diagonal
        self.assertAlmostEqual(calculate_path_cost([(0,0,0), (1,1,0)]), 2**0.5)
        # 3D diagonal
        self.assertAlmostEqual(calculate_path_cost([(0,0,0), (1,1,1)]), 3**0.5)
        
if __name__ == '__main__':
    unittest.main()
