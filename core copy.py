import json
import time
import random
import os
import sys
from datetime import datetime
from enum import Enum
from typing import List, Dict, Union, Optional
import config

# ==========================================
# 1. MOCK ENVIRONMENT & GLOBAL STATE
# ==========================================
# Προσομοιώνουμε την κατάσταση του δικτύου υποδομών και των συνεργείων.
# [cite: 371-389, 942-951]

WORLD_STATE = {
    "nodes": {
        "Node_Water_Pump_A": {"status": "Broken", "type": "Water", "population_affected": 5000, "criticality": "High"},
        "Node_Server_B": {"status": "Operational", "type": "Internet", "population_affected": 200, "criticality": "Low"},
        "Node_Power_Substation_C": {"status": "Broken", "type": "Power", "population_affected": 15000, "criticality": "Critical"},
        "Node_Relay_D": {"status": "Broken", "type": "Telecom", "population_affected": 1000, "criticality": "Medium"}
    },
    "crews": {
        "Crew_Alpha": {"status": "Available", "specialty": "General"},
        "Crew_Beta": {"status": "Available", "specialty": "Electrical"},
        "Crew_Gamma": {"status": "Busy", "specialty": "Water"}
    }
}

# ==========================================
# 2. TOOLS DEFINITION (Εργαλεία)
# ==========================================
# Υλοποίηση των 3 υποχρεωτικών εργαλείων με Type Hints και Docstrings.
# [cite: 722-728, 930-935]

def detect_failure_nodes() -> List[str]:
    """
    Scans the network infrastructure and returns a list of IDs for nodes
    that are currently in 'Broken' status.
    """
    failures = []
    for node_id, data in WORLD_STATE["nodes"].items():
        if data["status"] == "Broken":
            failures.append(node_id)
    return failures

def estimate_impact(node_id: str) -> Dict[str, Union[str, int]]:
    """
    Returns impact metrics for a specific node to help prioritize repairs.
    Args:
        node_id: The ID of the infrastructure node.
    Returns:
        dict: {'population_affected': int, 'criticality': str} or error.
    """
    node = WORLD_STATE["nodes"].get(node_id)
    if not node:
        return {"error": f"Node {node_id} not found."}

    return {
        "node_id": node_id,
        "type": node["type"],
        "population_affected": node["population_affected"],
        "criticality": node["criticality"]
    }

def assign_repair_crew(node_ids: List[str], crew_ids: List[str]) -> Dict[str, str]:
    """
    Assigns specific crews to specific nodes for repair.
    Args:
        node_ids: List of node IDs to repair.
        crew_ids: List of crew IDs to assign (must map 1-to-1 with nodes).
    Returns:
        dict: A status report of the assignments (Success/Failure).
    """
    results = {}

    # Validation logic (Simple 1-to-1 mapping for simulation)
    if len(node_ids) != len(crew_ids):
        return {"error": "Mismatch between number of nodes and crews."}

    for i in range(len(node_ids)):
        n_id = node_ids[i]
        c_id = crew_ids[i]

        node = WORLD_STATE["nodes"].get(n_id)
        crew = WORLD_STATE["crews"].get(c_id)

        if not node or not crew:
            results[f"{n_id}-{c_id}"] = "Failed: Invalid ID"
            continue

        if crew["status"] != "Available":
            results[f"{n_id}-{c_id}"] = f"Failed: {c_id} is Busy"
        else:
            # Execute Assignment (Update Global State)
            WORLD_STATE["nodes"][n_id]["status"] = "Repairing"
            WORLD_STATE["crews"][c_id]["status"] = "Busy"
            results[f"{n_id}-{c_id}"] = "Success: Crew dispatched"

    return {"assignment_report": results}

# ========================================
# 3 ACTUAL LLM, cognitive engineer:
# Χρήση πραγματικού LLM μέσω Ollama API / ώστε να τρέχουμε μικρά llm (2-4b parametres) για τον agent
import ollama

def llm_call(prompt: str, memory: dict) -> str:
    """Calls the local Ollama model (llama3.2:1b) to make a decision."""
    try:
        response = ollama.chat(
            model='llama3.2:1b',
            messages=[{'role': 'user', 'content': prompt}],
            format='json', # Force JSON output
            options={'temperature': 0.1} # Low temperature for more deterministic actions
        )
        return response['message']['content']
    except Exception as e:
        print(f"LLM Error: {e}")
        # Fallback safe response in case of LLM failure
        return json.dumps({
            "thought": f"LLM failed to respond: {str(e)}",
            "action": "finalize",
            "arguments": {}
        })

# ==========================================
# 4. AGENT FSM CLASS (Ο Πράκτορας)
# ==========================================
# [cite: 418-426, 955-969]

class AgentState(Enum):
    INIT = 0
    DETECT = 1
    ANALYZE = 2
    PLAN = 3
    ACT = 4
    FINAL = 5

class InfrastructureAgent:
    def __init__(self, max_steps=10):
        self.state = AgentState.INIT
        self.memory = {
            "context": {},      # Αποθήκευση βλαβών και metrics
            "history": []       # Καταγραφή ενεργειών
        }
        self.max_steps = max_steps
        self.step_count = 0

    def get_system_prompt(self):
        """Builds the prompt based on the current state (State Injection)."""
        base = "You are an Infrastructure Failure Management Agent.\n"
        base += "GOAL: Minimize social impact of network failures.\n"
        base += "RESPONSE FORMAT: JSON {thought, action, arguments}.\n"

        if self.state == AgentState.DETECT:
            return base + "PHASE: FAILURE DETECTION. Use tools to find broken nodes."
        elif self.state == AgentState.ANALYZE:
            return base + "PHASE: IMPACT ANALYSIS. Estimate impact for found failures."
        elif self.state == AgentState.PLAN:
            return base + "PHASE: REPAIR PLANNING. Assign available crews to critical nodes."
        else:
            return base

    def step(self):
        self.step_count += 1
        print(f"\n=== STEP {self.step_count} | STATE: {self.state.name} ===")

        # 1. THINK (Generate Prompt & Call LLM)
        prompt = self.get_system_prompt()
        print(f"[PROMPT]: {prompt.split('RESPONSE')[0]}...") # Τυπώνουμε συνοπτικά

        # LLM Call
        raw_response = llm_call(prompt, self.memory)
        try:
            decision = json.loads(raw_response)
            print(f"[RAW LLM]: {decision}")
        except:
            print("Error parsing JSON")
            return

        thought = decision.get("thought")
        action_name = decision.get("action")
        args = decision.get("arguments", {})

        print(f"[THOUGHT]: {thought}")
        print(f"[ACTION]: Calling {action_name} with {args}")

        # 2. ACT (Tool Execution & State Transitions)
        observation = None

        if action_name == "detect_failure_nodes":
            observation = detect_failure_nodes()
            self.memory['context']['failures'] = observation
            # Μετάβαση: Αν βρήκε βλάβες -> Analyze, αλλιώς -> Final
            if observation:
                self.state = AgentState.ANALYZE
            else:
                self.state = AgentState.FINAL

        elif action_name == "estimate_impact":
            observation = estimate_impact(**args)
            # Αποθήκευση του impact στη μνήμη
            if 'impact_data' not in self.memory['context']:
                self.memory['context']['impact_data'] = []
            self.memory['context']['impact_data'].append(observation)
            # Μετάβαση: Για το παράδειγμα, πάμε στο Plan μόλις έχουμε data
            self.state = AgentState.PLAN

        elif action_name == "assign_repair_crew":
            observation = assign_repair_crew(**args)
            # Μετάβαση: Ελέγχουμε αν πέτυχε η ανάθεση
            self.state = AgentState.FINAL # Τερματίζουμε για το demo, κανονικά θα υπήρχε Validate

        elif action_name == "finalize":
            observation = "Mission Accomplished."
            self.state = AgentState.FINAL

        print(f"[OBSERVATION]: {observation}")

    def save_run_data(self):
        """Saves the agent's memory and history to the runs folder."""
        if config and hasattr(config, 'runs_path') and os.path.exists(config.runs_path):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"run_{timestamp}.json"
            filepath = os.path.join(config.runs_path, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.memory, f, indent=4, ensure_ascii=False)
            print(f"\n[SYSTEM] Run data saved to: {filepath}")
        else:
            print("\n[SYSTEM] Warning: Could not save run data (runs_path not found).")

    def run(self):
        print("--- INFRASTRUCTURE AGENT STARTED ---")
        self.state = AgentState.DETECT # Ξεκινάμε από Detection

        while self.state != AgentState.FINAL and self.step_count < self.max_steps:
            self.step()
            time.sleep(1) # Μικρή καθυστέρηση για εφε

        print("\n--- AGENT FINISHED ---")
        print("Final World State (Failures should be 'Repairing'):")
        # Τυπώνουμε το state για να δείξουμε ότι η αλλαγή έγινε (State Persistence)
        print(json.dumps(WORLD_STATE["nodes"]["Node_Power_Substation_C"], indent=2))
        
        # Save data
        self.save_run_data()

# ==========================================
# 5. EXECUTION
# ==========================================
if __name__ == "__main__":
    agent = InfrastructureAgent()
    agent.run()