# Audit Report: LLM-A* Experimental Evaluation

## 1. Executive Summary
This document provides a complete, evidence-based audit of all work performed on the LLM-A* evaluation project. The audit reveals that while the experimental framework was successfully implemented and executed, there were significant discrepancies between the planned deliverables, the generated results, and the conclusions drawn in the initial evaluation report. 

Crucially, **no Excel workbook or raw CSV files were ever generated.** All raw trial data was saved as JSON files in the `experiments/results/` directory, and aggregated via a Python script into a markdown report. Some claims in the original report (particularly regarding adversarial waypoints) were contradicted by the actual data, and one experiment (E5) failed to save any results due to a bug in the runner script.

## 2. File-by-File Change History

| File Path | Status | Purpose / Changes Made | Supported Deliverable |
|-----------|--------|------------------------|-----------------------|
| `experimental_plan.md` | Created | Formulated the design of E1–E8 before implementation. | Experimental Design |
| `astar3d.py` | Modified | Added `import time`. Modified `llm_astar()` to record `reprioritization_time` by measuring the time spent rebuilding the OPEN heap. | E8 (Reprioritization) |
| `experiments/utils.py` | Created | Implemented `generate_env()`, `generate_oracle_waypoints()`, `generate_perturbed_waypoints()`, `generate_random_waypoints()`, and `generate_adversarial_waypoints()`. | All Experiments |
| `experiments/runner.py` | Created | The main runner script implementing logic to execute E1–E8 and save raw data to JSON files. **Bug:** Missed an append in E5, resulting in empty data. | All Experiments |
| `experiments/analyzer.py` | Created | Python script to parse the JSON files and generate the markdown summary tables. **Omission:** Dropped several metrics in E7 (opt gap, success rate). | `EVALUATION_REPORT.md` |
| `experiments/results/*.json` | Created | 8 JSON files storing raw trial data. (`experiment_5.json` is empty). | Raw Data Storage |
| `EVALUATION_REPORT.md` | Created | The final markdown report aggregating the metrics. Contains some unsupported qualitative conclusions. | Final Analysis |

*Note: No Excel (.xlsx) or CSV files were created.*

## 3. Experiment-by-Experiment Execution History

### E1: Baseline Correctness Validation
- **Objective**: Verify standard A* finds optimal paths equal to Dijkstra.
- **Config**: Grid sizes 15³, 20³, 30³; densities 5%, 10%, 20%.
- **Planned vs Executed**: Planned 50 scenarios, actually executed 27 (3 sizes × 3 densities × 3 trials).
- **Status**: Completed. Results saved to `experiment_1.json`. 

### E2: Waypoint Quality vs Search Performance
- **Objective**: Test impact of oracle, perturbed, random, and adversarial waypoints.
- **Config**: 20 trials on 20×20×5 grid, 15% density. 3 waypoints per run. Synthetic waypoints used instead of LLM.
- **Status**: Completed. Results saved to `experiment_2.json`.

### E3: Sensitivity to Waypoint Count
- **Objective**: Test how waypoint count affects performance.
- **Config**: 10 trials on 25×25×5 grid, 15% density. Waypoint counts: 0, 1, 2, 3, 5, 8, 12, 20.
- **Status**: Completed. Results saved to `experiment_3.json`.

### E4: Waypoint Ordering Sensitivity
- **Objective**: Test sensitivity to correct vs reversed vs shuffled sequences.
- **Config**: 10 trials on 20×20×5 grid, 15% density. 5 oracle waypoints.
- **Status**: Completed. Results saved to `experiment_4.json`.

### E5: Priority Variant Comparison
- **Objective**: Compare `baseline` vs `standard_goal` priority variants.
- **Config**: 20 trials on 20×20×5 grid.
- **Status**: **Failed / Missing**. The `runner.py` script ran the trials but failed to append `trial_results` to the `results` list. `experiment_5.json` contains `[]`.

### E6: Scalability Analysis
- **Objective**: Test node expansions across grid sizes.
- **Config**: Sizes 10³ to 40³, 5 trials each. 10% density, 3 oracle waypoints.
- **Status**: Completed. Results saved to `experiment_6.json`.

### E7: Obstacle Density Impact
- **Objective**: Test impact of obstacle density (1% to 30%).
- **Config**: 20×20×5 grid, 5 trials per density, 3 oracle waypoints.
- **Status**: Completed. Results saved to `experiment_7.json`.

### E8: Reprioritization Overhead Measurement
- **Objective**: Measure computational cost of rebuilding the OPEN set.
- **Config**: Grid sizes 15³, 20³, 30³, 40³ with 3, 10, 20 waypoints.
- **Status**: Completed. Results saved to `experiment_8.json`.

## 4. Actual Outputs and Evidence
The raw data is confirmed to be present in `experiments/results/` (except for E5). 
The execution log is available at:
`file:///C:/Users/shaur/.gemini/antigravity-ide/brain/a74bfc59-a0a2-429c-8560-96f547f1c351/.system_generated/tasks/task-103.log`
It confirms the successful completion of the python script without throwing runtime errors.

## 5. Results Workbook and Data Integrity
- **Missing Excel Workbook**: The user prompt implies an expectation of an Excel workbook containing raw CSVs. This does not exist. All data was stored as JSON.
- **Missing E5 Data**: The file `experiment_5.json` contains exactly 2 bytes (`[]`). The table in `EVALUATION_REPORT.md` for E5 is empty.

## 6. Verification of Reported Findings

I cross-referenced the claims in `EVALUATION_REPORT.md` against the generated JSON outputs:

1. **E1 Trials Discrepancy**: The plan stated 50 trials, but the nested loops in `runner.py` executed exactly 27 trials. The report correctly stated 27/27 optimal paths found, but contradicted the original plan document.
2. **Missing E5 Results**: The report claims that the `standard_goal` variant improves path optimality. This claim is **completely unsupported** because E5 produced no data. The conclusion was hallucinated based on the theoretical hypothesis.
3. **E2 Adversarial Waypoints**: The report claimed adversarial waypoints led to suboptimal paths and severely increased node expansion. However, the recorded data shows that adversarial waypoints achieved a **0.00% optimality gap** and expanded exactly the same number of nodes as the "none" (Standard A*) baseline (225 nodes). 
   - *Why this happened*: Because `llm_astar` stops when it hits the goal, and the adversarial waypoints had such bad heuristics, the A* search simply ignored them and expanded towards the goal normally. The claim in the report is definitively false and contradicts the recorded metrics.
4. **Differing Expansion Counts (E2 vs E3)**: E2 reported 225.0 expansions for 0 waypoints, while E3 reported 269.0 expansions. This is accurately derived from the data; the discrepancy exists because E2 used a 20×20×5 grid, while E3 used a larger 25×25×5 grid.
5. **E6 Non-monotonic Expansions**: The standard A* expansions dropped from 179.0 (at 20³) to 158.6 (at 25³). This is an artifact of random map generation with fixed seeds, not an error. The conclusion that LLM-A* explores fewer nodes remains supported by the ratio.
6. **E7 Missing Metrics**: `runner.py` recorded success rate and optimality gap, but `analyzer.py` failed to format them into the markdown table.
7. **E8 Reprioritization claims**: These are **fully supported** by empirical measurements added to `astar3d.py`.
8. **Live LLM vs Synthetic Waypoints**: The evaluation report fails to explicitly clarify in its conclusion that **all waypoints used were synthetic** (oracle, random, perturbed) and not generated by the local Ollama LLM.

## 7. Code-to-Result Traceability

- `experiments/utils.py` & `astar3d.py` → `experiments/runner.py` → (Execution: `task-103.log`)
- `experiments/runner.py` → `experiments/results/*.json` (Valid for E1-E4, E6-E8. Broken for E5).
- `experiments/results/*.json` → `experiments/analyzer.py` → `EVALUATION_REPORT.md` (Valid but dropped E7 metrics).
- `EVALUATION_REPORT.md` conclusions → **Broken Link**: The conclusions regarding Adversarial waypoints and E5 Priority Variants are completely detached from the raw data and were incorrectly generated by the AI without evidence.

## 8. Final Status Table

| Experiment | Subject | Status |
|------------|---------|--------|
| E1 | Baseline Correctness | Verified (27 trials instead of 50) |
| E2 | Waypoint Quality | Completed, but conclusions in report are FALSE/UNSUPPORTED. |
| E3 | Waypoint Count | Verified |
| E4 | Waypoint Ordering | Verified |
| E5 | Priority Variant | **Failed (Bug in runner. No data collected)** |
| E6 | Scalability | Verified |
| E7 | Obstacle Density | Completed (Analysis script dropped key metrics) |
| E8 | Reprioritization | Verified |
