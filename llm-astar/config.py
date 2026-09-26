# Configuration for LLM-A* Path Planning

GRID_SIZE = (100, 100, 50)
START = (2, 3, 1)
GOAL = (95, 95, 45)
NUM_OBSTACLES = 25000

OLLAMA_URL = "http://localhost:11434/api/generate"
# You might need to change this model name to the one you have downloaded (e.g., 'llama3', 'mistral')
OLLAMA_MODEL = "qwen2.5:7b" 
