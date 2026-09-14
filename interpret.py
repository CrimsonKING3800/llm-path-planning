"""
interpret.py

This module interfaces with a local Ollama LLM to interpret simulation
results from the multi-agent path planning pipeline. It constructs a specific
prompt from the given objective and simulation results and asks the LLM
for an explanation.
"""

import json
import sys
import requests

def _call_ollama(prompt: str, model: str = "qwen2.5:7b", timeout: int = 60) -> str:
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_predict": 2048
        }
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()["response"]
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Failed to communicate with Ollama: {e}")
        print("Please ensure Ollama is running (`ollama serve`).")
        raise SystemExit(1)

PROMPT_TEMPLATE = """You designed a multi-agent path planning algorithm for this objective: {objective}.

Execution results:
- Success: {success}
- Collisions detected: {collisions}
- Makespan: {makespan} steps
- Total distance: {total_distance}
- Per-agent steps: {steps_per_agent}

Explain in plain language:
1. Did the algorithm achieve the stated objective?
2. If there were failures/collisions, what likely caused them?
3. Suggest one concrete change to the algorithm to improve the result.
"""

def interpret_results(objective: dict, sim_results: dict) -> str:
    """
    Interprets simulation results using the configured LLM backend.

    Args:
        objective (dict): A dictionary describing the algorithm's objective.
        sim_results (dict): A dictionary containing the execution results. Expected keys:
            - success (bool)
            - collisions (int)
            - makespan (int)
            - total_distance (float or int)
            - steps_per_agent (dict or list)

    Returns:
        str: The plain language interpretation from the LLM.
        
    Raises:
        SystemExit: If the Ollama server is unreachable.
    """
    prompt = PROMPT_TEMPLATE.format(
        objective=json.dumps(objective),
        success=sim_results.get("success", False),
        collisions=sim_results.get("collisions", 0),
        makespan=sim_results.get("makespan", 0),
        total_distance=sim_results.get("total_distance", 0),
        steps_per_agent=json.dumps(sim_results.get("steps_per_agent", {}))
    )
    
    return _call_ollama(prompt)

if __name__ == "__main__":
    # Sample data for testing the interpretation module
    sample_objective = {
        "description": "Navigate 3 agents from start to goal locations in a grid environment while avoiding obstacles and each other."
    }
    
    sample_results = {
        "success": False,
        "collisions": 2,
        "makespan": 15,
        "total_distance": 32.5,
        "steps_per_agent": {"agent_0": 10, "agent_1": 15, "agent_2": 11}
    }
    
    print("Calling LLM to interpret results...")
    interpretation = interpret_results(sample_objective, sample_results)
    
    print("\n--- LLM Interpretation ---")
    print(interpretation)
    print("--------------------------")
