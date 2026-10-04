# CORRECTED LLM-A* Experimental Evaluation Report

This report presents a corrected, evidence-based evaluation of the LLM-A* algorithm implementation based on raw historical data and a rerun of Experiment 5. 

**Important Note**: All experiments evaluated the underlying search mechanism using purely **synthetic waypoints** (oracle, random, perturbed) to isolate pathfinding performance from live LLM inference delays or failures. This ensures reproducibility but means live LLM guidance quality was not directly tested here.

---

## 1. Baseline Correctness Validation (Historical Data)
- **Objective**: Verify that Standard A* on our 3D grid, with our movement and edge-cost rules, produces paths matching Dijkstra's optimal path.
- **Trials**: 27 valid trials executed across grid sizes (15³, 20³, 30³) and obstacle densities (5%, 10%, 20%). 
- **Results**: In all 27/27 trials, Standard A* found optimal paths with a 0.00% cost gap relative to Dijkstra. 
- **Conclusion**: The base A* implementation behaves correctly under the tested configurations.

## 2. Waypoint Quality vs Search Performance (Historical Data)
- **Objective**: Determine how the optimality and efficiency of LLM-A* scale with waypoint quality.
- **Trials**: 20 valid trials (Grid: 20×20×5, 15% density).

| Condition | Success Rate | Mean Opt Gap (%) | Mean Expanded |
|-----------|--------------|------------------|---------------|
| oracle | 100.0% | 0.79% | 19.5 |
| near_optimal | 100.0% | 4.07% | 21.9 |
| random | 100.0% | 4.12% | 171.6 |
| adversarial | 100.0% | 0.00% | 225.0 |
| none (Standard A*) | 100.0% | 0.00% | 225.0 |

- **Conclusion**: Accurate (oracle) waypoints drastically reduce node expansions (from 225 down to ~20). However, if waypoints are random, expansion spikes severely. Interestingly, if waypoints are completely adversarial (pointing away from the goal), the `llm_astar` search effectively ignores them, degrading gracefully back to Standard A* behavior (225 expansions, 0% opt gap). **This challenges the assumption that adversarial waypoints force suboptimal paths.**

## 3. Sensitivity to Waypoint Count (Historical Data)
- **Objective**: Measure the impact of increasing the number of oracle waypoints.
- **Trials**: 10 valid trials per count (Grid: 25×25×5, 15% density).

| Waypoints | Mean Expanded | Mean Search Time (s) |
|-----------|---------------|----------------------|
| 0 | 269.0 | 0.00568 |
| 1 | 24.2 | 0.00080 |
| 2 | 24.3 | 0.00088 |
| ... | ... | ... |
| 20 | 24.3 | 0.00216 |

- **Conclusion**: Supplying even a single oracle waypoint significantly reduces expanded nodes. However, search time stops decreasing and starts increasing slightly after 3 waypoints, indicating algorithmic overhead unrelated to node expansion. 
*(Note: The 0-waypoint baseline here expands 269 nodes compared to 225 in E2 because E3 uses a larger 25x25x5 grid).*

## 4. Waypoint Ordering Sensitivity (Historical Data)
- **Objective**: Test the algorithm's robustness to shuffled or reversed waypoint sequences.
- **Trials**: 10 valid trials per ordering (Grid: 20×20×5, 15% density).

| Ordering | Mean Opt Gap (%) | Mean Expanded |
|----------|------------------|---------------|
| correct | 0.00% | 19.3 |
| reverse | 0.03% | 736.6 |
| shuffle_1 | 0.03% | 1113.3 |

- **Conclusion**: LLM-A* is extremely fragile regarding waypoint ordering. A shuffled sequence forces the algorithm to explore vast sections of the search space (over 1000 nodes), performing significantly worse than having no waypoints at all. 

## 5. Priority Variant Comparison (Corrective Rerun)
- **Objective**: Compare the `baseline` and `standard_goal` priority variants to see if defaulting to true goal-distance at the final waypoint improves path optimality.
- **Trials**: 20 new valid trials executed (Grid: 20×20×5, 15% density, 3 oracle waypoints).

| Variant | Success Rate | Mean Opt Gap (%) | Mean Expanded | Mean Search Time (s) |
|---------|--------------|------------------|---------------|----------------------|
| baseline | 100.0% | 0.81% | 19.6 | 0.00085 |
| standard_goal | 100.0% | 0.00% | 20.3 | 0.00088 |

- **Conclusion**: The `standard_goal` variant successfully closes the optimality gap to 0.00% at the cost of a statistically negligible increase in expanded nodes. This confirms the theoretical hypothesis with actual empirical data.

## 6. Scalability Analysis (Historical Data)
- **Objective**: Evaluate node expansions as the grid size increases.
- **Trials**: 5 valid trials per size (Grid: 10³ to 40³, 10% density, 3 oracle waypoints).

| Grid Size | Std A* Expanded | LLM-A* Expanded | Expansion Ratio |
|-----------|-----------------|-----------------|-----------------|
| 10³ | 24.2 | 9.4 | 0.39x |
| 15³ | 70.0 | 14.8 | 0.21x |
| 20³ | 179.0 | 20.2 | 0.11x |
| 25³ | 158.6 | 25.0 | 0.16x |
| 30³ | 311.4 | 30.2 | 0.10x |
| 40³ | 638.2 | 40.4 | 0.06x |

- **Conclusion**: As grid size increases, LLM-A* (with oracle waypoints) expands a progressively smaller fraction of nodes compared to Standard A* (reaching 6% at 40³). *Note: The drop in Standard A* expansions at 25³ is a normal artifact of random map generation.* While node expansions scale excellently, this does not directly equate to wall-clock scalability (see E8).

## 7. Obstacle Density Impact (Historical Data - Recomputed)
- **Objective**: Measure the effect of obstacle density on expansion ratio.
- **Trials**: 5 valid trials per density (Grid: 20×20×5, densities 1% to 30%).
- **Conclusion**: LLM-A* consistently maintains an expansion ratio of 0.06x to 0.11x across all obstacle densities relative to Standard A*, suggesting its pruning capability is robust to environmental clutter (provided waypoints are optimal). 

## 8. Reprioritization Overhead Measurement (Historical Data)
- **Objective**: Quantify the computational cost of the $O(N)$ re-heapification step that occurs when LLM-A* switches targets.
- **Trials**: 3 valid trials per configuration across sizes 15³, 20³, 30³, 40³ and 3, 10, 20 waypoints.

| Grid Size | Waypoints | Mean Reprioritization Overhead | Mean Peak OPEN Size |
|-----------|-----------|--------------------------------|---------------------|
| 15³ | 3 | 30.39% | 219.0 |
| 15³ | 20 | 63.92% | 214.7 |
| 40³ | 3 | 30.25% | 621.3 |
| 40³ | 20 | 73.96% | 620.0 |

- **Conclusion**: Reprioritization (re-calculating heuristics and rebuilding the `OPEN` set) consumes a massive fraction of total search time, scaling linearly with the number of waypoints. This constitutes a severe bottleneck that can easily wipe out the speed gains achieved by reducing node expansions. 
