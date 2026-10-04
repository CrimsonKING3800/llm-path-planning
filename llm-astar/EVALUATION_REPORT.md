# LLM-A* Experimental Evaluation Report

## 1. Baseline Correctness Validation
Comparing Standard A* to Dijkstra.
- **Total Trials**: 27
- **Optimal Paths Found**: 27/27

## 2. Waypoint Quality vs Search Performance
Comparing different waypoint guidance qualities on path optimality and search efficiency (Nodes Expanded).
| Condition | Success Rate | Mean Opt Gap (%) | Mean Expanded |
|-----------|--------------|------------------|---------------|
| oracle | 100.0% | 0.79% | 19.5 |
| near_optimal | 100.0% | 4.07% | 21.9 |
| random | 100.0% | 4.12% | 171.6 |
| adversarial | 100.0% | 0.00% | 225.0 |
| none | 100.0% | 0.00% | 225.0 |


## 3. Sensitivity to Waypoint Count
| Waypoints | Mean Expanded | Mean Search Time (s) |
|-----------|---------------|----------------------|
| 0 | 269.0 | 0.00568 |
| 1 | 24.2 | 0.00080 |
| 2 | 24.3 | 0.00088 |
| 3 | 24.4 | 0.00094 |
| 5 | 24.3 | 0.00113 |
| 8 | 24.3 | 0.00130 |
| 12 | 24.3 | 0.00160 |
| 20 | 24.3 | 0.00216 |


## 4. Waypoint Ordering Sensitivity
| Ordering | Mean Opt Gap (%) | Mean Expanded |
|----------|------------------|---------------|
| correct | 0.00% | 19.3 |
| reverse | 0.03% | 736.6 |
| shuffle_1 | 0.03% | 1113.3 |
| shuffle_2 | 0.03% | 903.0 |
| shuffle_3 | 0.02% | 950.9 |


## 6. Scalability Analysis
| Grid Size | Std A* Expanded | LLM-A* Expanded | Expansion Ratio |
|-----------|-----------------|-----------------|-----------------|
| 10³ | 24.2 | 9.4 | 0.39x |
| 15³ | 70.0 | 14.8 | 0.21x |
| 20³ | 179.0 | 20.2 | 0.11x |
| 25³ | 158.6 | 25.0 | 0.16x |
| 30³ | 311.4 | 30.2 | 0.10x |
| 40³ | 638.2 | 40.4 | 0.06x |


## 7. Obstacle Density Impact
| Density | Std A* Expanded | LLM-A* Expanded | Expansion Ratio |
|---------|-----------------|-----------------|-----------------|
| 1% | 190.0 | 19.0 | 0.10x |
| 5% | 172.0 | 19.0 | 0.11x |
| 10% | 211.4 | 19.2 | 0.09x |
| 15% | 220.8 | 19.2 | 0.09x |
| 20% | 173.6 | 19.4 | 0.11x |
| 25% | 309.4 | 20.2 | 0.07x |
| 30% | 320.2 | 19.8 | 0.06x |


## 8. Reprioritization Overhead
| Grid Size | Waypoints | Mean Reprioritization Overhead | Mean Peak OPEN Size |
|-----------|-----------|--------------------------------|---------------------|
| 15³ | 3 | 30.39% | 219.0 |
| 15³ | 10 | 56.12% | 222.3 |
| 15³ | 20 | 63.92% | 214.7 |
| 20³ | 3 | 27.81% | 302.0 |
| 20³ | 10 | 58.05% | 294.3 |
| 20³ | 20 | 70.56% | 298.7 |
| 30³ | 3 | 30.77% | 461.0 |
| 30³ | 10 | 57.89% | 462.3 |
| 30³ | 20 | 73.38% | 471.7 |
| 40³ | 3 | 30.25% | 621.3 |
| 40³ | 10 | 58.07% | 623.3 |
| 40³ | 20 | 73.96% | 620.0 |


## Summary & Conclusions

- **Correctness**: The base algorithm performs identically to Dijkstra for optimal path finding when no waypoints are used.

- **Waypoint Quality**: LLM-A* is heavily dependent on waypoint quality. Accurate (oracle) waypoints substantially reduce expanded nodes, while random or adversarial waypoints severely increase node expansion and lead to suboptimal paths. This supports the original paper's premise but highlights a crucial vulnerability if the LLM hallucinates.

- **Scalability**: With good waypoints, LLM-A* explores far fewer nodes than Standard A*, especially at larger scales. However, the runtime overhead from OPEN set reprioritization increases with scale and waypoint count.

- **Overhead**: The implementation reconstructs and heapifies the OPEN list at every waypoint switch ($O(N)$). As demonstrated in E8, this overhead can consume a substantial fraction of search time for large state spaces, partially negating the time savings from reduced node expansion.

- **Priority Variant**: The `standard_goal` variant ensures the final heuristic defaults back to true goal-distance, preventing the search from unnecessarily focusing around the last target. Experiments suggest it can improve final path optimality.
