import os
import json
import pandas as pd
import matplotlib.pyplot as plt

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
DELIVERABLES_DIR = os.path.join(os.path.dirname(__file__), "deliverables")
os.makedirs(DELIVERABLES_DIR, exist_ok=True)

def load_json(name):
    path = os.path.join(RESULTS_DIR, f"{name}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        return json.load(f)

def generate_csv_and_excel():
    excel_path = os.path.join(RESULTS_DIR, "LLM_Astar_Experimental_Results.xlsx")
    writer = pd.ExcelWriter(excel_path, engine='openpyxl')
    
    # Configuration sheet
    config_df = pd.DataFrame([
        {"Parameter": "GRID_SIZE", "Value": "(100, 100, 50) configured, dynamic per exp"},
        {"Parameter": "PRIORITY_VARIANT", "Value": "baseline (except E5)"},
        {"Parameter": "CLOSED_NODE_VARIANT", "Value": "baseline"},
        {"Parameter": "LLM", "Value": "Synthetic waypoints used for reproducibility (Ollama bypassed)"}
    ])
    config_df.to_excel(writer, sheet_name="Configurations", index=False)
    
    # E1
    e1 = load_json("experiment_1")
    if e1:
        e1_df = pd.DataFrame(e1)
        e1_df.to_csv(os.path.join(DELIVERABLES_DIR, "e1_baseline.csv"), index=False)
        e1_df.to_excel(writer, sheet_name="E1_Baseline", index=False)
        
    # E2
    e2 = load_json("experiment_2")
    if e2:
        e2_rows = []
        for trial in e2:
            for cond, data in trial['runs'].items():
                e2_rows.append({
                    "trial": trial['trial'],
                    "optimal_cost": trial['optimal_cost'],
                    "condition": cond,
                    "path_found": data['path_found'],
                    "path_cost": data['path_cost'],
                    "optimality_gap": data['optimality_gap'],
                    "expanded": data['expanded'],
                    "generated": data['generated']
                })
        e2_df = pd.DataFrame(e2_rows)
        e2_df.to_csv(os.path.join(DELIVERABLES_DIR, "e2_waypoint_quality.csv"), index=False)
        e2_df.to_excel(writer, sheet_name="E2_Quality", index=False)
        
        # Plot E2
        plt.figure(figsize=(10,6))
        e2_df.boxplot(column='expanded', by='condition')
        plt.title('Node Expansions by Waypoint Quality')
        plt.suptitle('')
        plt.ylabel('Nodes Expanded')
        plt.xlabel('Condition')
        plt.savefig(os.path.join(DELIVERABLES_DIR, "e2_quality_plot.png"))
        plt.close('all')

    # E3
    e3 = load_json("experiment_3")
    if e3:
        e3_rows = []
        for trial in e3:
            for count, data in trial['runs'].items():
                e3_rows.append({
                    "trial": trial['trial'],
                    "optimal_cost": trial['optimal_cost'],
                    "waypoint_count": int(count),
                    "path_found": data['path_found'],
                    "path_cost": data['path_cost'],
                    "optimality_gap": data['optimality_gap'],
                    "expanded": data['expanded'],
                    "search_time": data.get('search_time', None)
                })
        e3_df = pd.DataFrame(e3_rows)
        e3_df.to_csv(os.path.join(DELIVERABLES_DIR, "e3_waypoint_count.csv"), index=False)
        e3_df.to_excel(writer, sheet_name="E3_Count", index=False)

    # E4
    e4 = load_json("experiment_4")
    if e4:
        e4_rows = []
        for trial in e4:
            for cond, data in trial['runs'].items():
                e4_rows.append({
                    "trial": trial['trial'],
                    "optimal_cost": trial['optimal_cost'],
                    "ordering": cond,
                    "path_found": data['path_found'],
                    "path_cost": data['path_cost'],
                    "optimality_gap": data['optimality_gap'],
                    "expanded": data['expanded']
                })
        e4_df = pd.DataFrame(e4_rows)
        e4_df.to_csv(os.path.join(DELIVERABLES_DIR, "e4_ordering.csv"), index=False)
        e4_df.to_excel(writer, sheet_name="E4_Ordering", index=False)

    # E5
    e5 = load_json("experiment_5_rerun")
    if e5:
        e5_rows = []
        for trial in e5:
            for cond, data in trial['runs'].items():
                e5_rows.append({
                    "trial": trial['trial'],
                    "optimal_cost": trial['optimal_cost'],
                    "variant": cond,
                    "path_found": data['path_found'],
                    "path_cost": data['path_cost'],
                    "optimality_gap": data['optimality_gap'],
                    "expanded": data['expanded'],
                    "search_time": data.get('search_time', None)
                })
        e5_df = pd.DataFrame(e5_rows)
        e5_df.to_csv(os.path.join(DELIVERABLES_DIR, "e5_priority_variant.csv"), index=False)
        e5_df.to_excel(writer, sheet_name="E5_Variants_Rerun", index=False)

    # E6
    e6 = load_json("experiment_6")
    if e6:
        e6_df = pd.DataFrame(e6)
        e6_df.to_csv(os.path.join(DELIVERABLES_DIR, "e6_scalability.csv"), index=False)
        e6_df.to_excel(writer, sheet_name="E6_Scalability", index=False)
        
        # Plot E6
        e6_agg = e6_df.groupby('size')[['std_expanded', 'llm_expanded']].mean().reset_index()
        plt.figure(figsize=(10,6))
        plt.plot(e6_agg['size'], e6_agg['std_expanded'], label='Standard A*', marker='o')
        plt.plot(e6_agg['size'], e6_agg['llm_expanded'], label='LLM-A*', marker='s')
        plt.title('Node Expansions vs Grid Size (10% Obstacles)')
        plt.xlabel('Grid Size (N for NxNxN)')
        plt.ylabel('Mean Nodes Expanded')
        plt.legend()
        plt.savefig(os.path.join(DELIVERABLES_DIR, "e6_scalability_plot.png"))
        plt.close('all')

    # E7
    e7 = load_json("experiment_7")
    if e7:
        e7_df = pd.DataFrame(e7)
        e7_df.to_csv(os.path.join(DELIVERABLES_DIR, "e7_obstacle_density.csv"), index=False)
        e7_df.to_excel(writer, sheet_name="E7_Density", index=False)

    # E8
    e8 = load_json("experiment_8")
    if e8:
        e8_df = pd.DataFrame(e8)
        # Add open_at_switches length
        e8_df['num_switches'] = e8_df['open_at_switches'].apply(len)
        e8_df.drop('open_at_switches', axis=1, inplace=True)
        e8_df.to_csv(os.path.join(DELIVERABLES_DIR, "e8_reprioritization.csv"), index=False)
        e8_df.to_excel(writer, sheet_name="E8_Reprioritization", index=False)
        
        # Plot E8
        e8_agg = e8_df.groupby('count')['reprio_fraction'].mean().reset_index()
        plt.figure(figsize=(10,6))
        plt.bar(e8_agg['count'].astype(str), e8_agg['reprio_fraction'] * 100)
        plt.title('Mean Reprioritization Overhead by Waypoint Count')
        plt.xlabel('Number of Waypoints')
        plt.ylabel('% of Search Time Spent Reprioritizing')
        plt.savefig(os.path.join(DELIVERABLES_DIR, "e8_overhead_plot.png"))
        plt.close('all')

    writer.close()
    print(f"Generated deliverables in {DELIVERABLES_DIR} and {excel_path}")

if __name__ == "__main__":
    generate_csv_and_excel()
