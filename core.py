import json, time, os
from datetime import datetime
from enum import Enum
from typing import List, Dict, Union
import config
import ollama

# ==========================================
# 1. MOCK ENVIRONMENT - ΕΠΕΚΤΕΤΑΣΜΕΝΟ
# ==========================================
WORLD_STATE = {
    "nodes": {
        "Node_Water_Pump_A": {"status": "Broken", "type": "Water", "population_affected": 5000, "criticality": "High"},
        "Node_Server_B": {"status": "Operational", "type": "Internet", "population_affected": 200, "criticality": "Low"},
        "Node_Power_Substation_C": {"status": "Broken", "type": "Power", "population_affected": 15000, "criticality": "Critical"},
        "Node_Relay_D": {"status": "Operational", "type": "Telecom", "population_affected": 1000, "criticality": "Medium"},
        "Node_Hospital_Generator": {"status": "Broken", "type": "Power", "population_affected": 3000, "criticality": "Critical"},
        "Node_Water_Treatment": {"status": "Broken", "type": "Water", "population_affected": 8000, "criticality": "High"}
    },
    "crews": {
        "Crew_Alpha": {"status": "Available", "specialty": "General"},
        "Crew_Beta": {"status": "Available", "specialty": "Electrical"},
        "Crew_Gamma": {"status": "Available", "specialty": "Water"},
        "Crew_Delta": {"status": "Busy", "specialty": "General"}
    }
}

# ==========================================
# 2. TOOLS
# ==========================================
def detect_failure_nodes() -> List[str]:
    return [n for n, d in WORLD_STATE["nodes"].items() if d["status"] == "Broken"]

def estimate_impact(node_id: str) -> Dict[str, Union[str, int]]:
    if node := WORLD_STATE["nodes"].get(node_id):
        return {"node_id": node_id, "type": node["type"], 
                "population_affected": node["population_affected"], "criticality": node["criticality"]}
    return {"error": "Node not found"}

def assign_repair_crew(node_ids: List[str], crew_ids: List[str]) -> Dict[str, str]:
    results = {}
    for n, c in zip(node_ids, crew_ids):
        crew_status = WORLD_STATE["crews"][c]["status"]
        if crew_status != "Available":
            results[f"{c}->{n}"] = f"Failed (Crew {crew_status})"
        else:
            WORLD_STATE["nodes"][n]["status"] = "Repairing"
            WORLD_STATE["crews"][c]["status"] = "Busy"  # 🚨 Το crew γίνεται Busy!
            results[f"{c}->{n}"] = "Success"
            print(f"  🛠️  Crew {c} is now BUSY repairing {n}")
    return results

def check_crew_availability() -> Dict[str, str]:
    """Check status of all crews"""
    return {c: d["status"] for c, d in WORLD_STATE["crews"].items()}

# ==========================================
# 3. LLM INTERFACE
# ==========================================
def llm_call(system_prompt: str, user_context: str) -> Dict:
    try:
        response = ollama.chat(model="lfm2.5-thinking:1.2b", messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_context}
        ], format="json", options={"temperature": 0.0})
        return json.loads(response["message"]["content"])
    except:
        return {"thought": "LLM error", "action": "none", "arguments": {}}

# ==========================================
# 4. FSM & AGENT
# ==========================================
class AgentState(Enum):
    DETECT, ANALYZE, PLAN, ACT, FINAL = range(1, 6)

class InfrastructureAgent:
    def __init__(self, max_steps=20):
        self.state = AgentState.DETECT
        self.step_count = 0
        self.max_steps = max_steps
        self.memory = {"context": {}, "history": []}

    def get_system_prompt(self, remaining_nodes=None):
        base = """You are an Infrastructure Failure Management Agent.
GOAL: Minimize social impact by repairing broken nodes.

IMPORTANT: When a crew is assigned to a node, it becomes BUSY and cannot be used again.

STATE RULES:
1. DETECT: Call detect_failure_nodes
2. ANALYZE: Call estimate_impact ONCE per node
3. PLAN: No tool calls (system creates plan based on available crews)
4. ACT: Call assign_repair_crew

PRIORITY: Critical > High > Medium > Low (then by population)

RESPONSE FORMAT (JSON ONLY):
{
  "thought": "reasoning",
  "action": "tool_name",
  "arguments": {}
}
"""
        
        prompts = {
            AgentState.DETECT: "CURRENT STATE: DETECT\nACTION: detect_failure_nodes",
            AgentState.ANALYZE: f"CURRENT STATE: ANALYZE\nREMAINING: {remaining_nodes or 'Analyze one node'}\nACTION: estimate_impact",
            AgentState.PLAN: "CURRENT STATE: PLAN\nACTION: none",
            AgentState.ACT: "CURRENT STATE: ACT\nACTION: assign_repair_crew"
        }
        
        return base + "\n" + prompts.get(self.state, "")

    def step(self):
        self.step_count += 1
        print(f"\n{'='*50}\nSTEP {self.step_count} | STATE: {self.state.name}\n{'='*50}")

        # Get current status
        available_crews = [c for c, d in WORLD_STATE["crews"].items() if d["status"] == "Available"]
        busy_crews = [c for c, d in WORLD_STATE["crews"].items() if d["status"] == "Busy"]
        failures = self.memory["context"].get("failures", [])
        analyzed = [r["node_id"] for r in self.memory["context"].get("impact_reports", [])]
        remaining = [n for n in failures if n not in analyzed] if self.state == AgentState.ANALYZE else []
        
        context = {
            "state": self.state.name,
            "failed_nodes": failures,
            "analyzed_nodes": analyzed,
            "remaining_to_analyze": remaining,
            "available_crews": available_crews,
            "busy_crews": busy_crews,
            "all_crews_status": check_crew_availability()
        }
        
        print(f"[CONTEXT]: {json.dumps(context, indent=2)}")
        
        # Get LLM decision
        decision = llm_call(self.get_system_prompt(remaining), json.dumps(context))
        print(f"[DECISION]: {json.dumps(decision, indent=2)}")
        
        action = decision.get("action", "none")
        args = decision.get("arguments", {})
        thought = decision.get("thought", "No reasoning")
        
        print(f"[THOUGHT]: {thought}")
        print(f"[ACTION]: {action}")
        
        # Execute based on state
        observation = self.execute_state_action(action, args, failures, analyzed, remaining, available_crews)
        
        print(f"[OBSERVATION]: {observation}")
        
        # Save history
        self.memory["history"].append({
            "step": self.step_count, "state": self.state.name,
            "thought": thought, "action": action, "observation": observation,
            "crews_status": check_crew_availability()
        })

    def execute_state_action(self, action, args, failures, analyzed, remaining, available_crews):
        # DETECT state
        if self.state == AgentState.DETECT:
            if action != "detect_failure_nodes":
                action = "detect_failure_nodes"
            
            obs = detect_failure_nodes()
            self.memory["context"]["failures"] = obs
            self.state = AgentState.ANALYZE if obs else AgentState.FINAL
            return f"Found {len(obs)} broken nodes: {obs}"
        
        # ANALYZE state
        elif self.state == AgentState.ANALYZE:
            node_id = args.get("node_id")
            
            # Auto-correct if wrong action
            if action != "estimate_impact" or not node_id:
                node_id = remaining[0] if remaining else None
            
            if node_id and node_id in failures and node_id not in analyzed:
                obs = estimate_impact(node_id)
                self.memory["context"].setdefault("impact_reports", []).append(obs)
                
                # Check if all analyzed
                new_analyzed = [r["node_id"] for r in self.memory["context"].get("impact_reports", [])]
                if all(n in new_analyzed for n in failures):
                    self.state = AgentState.PLAN
                    return f"✅ All {len(failures)} nodes analyzed. Moving to PLAN"
                return f"✅ Analyzed {node_id}: {obs['criticality']}, {obs['population_affected']} people"
            else:
                return f"❌ Cannot analyze {node_id}"
        
        # PLAN state
        elif self.state == AgentState.PLAN:
            impacts = self.memory["context"].get("impact_reports", [])
            
            if not impacts:
                self.state = AgentState.FINAL
                return "No impacts to plan"
            
            # Sort by priority
            priority = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}
            impacts.sort(key=lambda x: (priority[x["criticality"]], x["population_affected"]), reverse=True)
            
            print(f"📊 PRIORITY LIST:")
            for i, imp in enumerate(impacts):
                print(f"  {i+1}. {imp['node_id']}: {imp['criticality']} ({imp['population_affected']} people)")
            
            # Create plan with available crews
            plan = []
            for i, imp in enumerate(impacts):
                if i < len(available_crews):
                    plan.append({"node": imp["node_id"], "crew": available_crews[i]})
                else:
                    print(f"  ⚠️  No crew for {imp['node_id']} ({len(available_crews)} crews available)")
            
            self.memory["context"]["repair_plan"] = plan
            
            if plan:
                self.state = AgentState.ACT
                return f"📋 Plan: {plan}"
            else:
                self.state = AgentState.FINAL
                return "❌ No available crews for repair"
        
        # ACT state
        elif self.state == AgentState.ACT:
            plan = self.memory["context"].get("repair_plan", [])
            
            # Use plan from memory if LLM didn't provide proper args
            if action != "assign_repair_crew" or not args.get("node_ids"):
                node_ids = [p["node"] for p in plan]
                crew_ids = [p["crew"] for p in plan]
            else:
                node_ids = args.get("node_ids", [])
                crew_ids = args.get("crew_ids", [])
            
            print(f"🚀 EXECUTING REPAIR PLAN:")
            for n, c in zip(node_ids, crew_ids):
                print(f"  ▶️  Assigning {c} to repair {n}")
            
            obs = assign_repair_crew(node_ids, crew_ids)
            self.state = AgentState.FINAL
            
            # Check how many crews are now busy
            busy_count = len([c for c, d in WORLD_STATE["crews"].items() if d["status"] == "Busy"])
            return f"{obs} | {busy_count} crews now BUSY"
        
        return "Invalid state"

    def run(self):
        print(f"\n{'='*50}")
        print("🏗️  INFRASTRUCTURE FAILURE MANAGEMENT AGENT")
        print(f"{'='*50}")
        
        initial_broken = detect_failure_nodes()
        initial_crews = check_crew_availability()
        
        print(f"\n📊 INITIAL STATUS:")
        print(f"  Broken nodes: {len(initial_broken)} → {initial_broken}")
        print(f"  Crew status: {initial_crews}")
        print(f"  Available crews: {[c for c, s in initial_crews.items() if s == 'Available']}")
        
        while self.state != AgentState.FINAL and self.step_count < self.max_steps:
            self.step()
            time.sleep(0.5)
        
        # Final report
        print(f"\n{'='*50}")
        print("🏁 AGENT FINISHED")
        print(f"{'='*50}")
        
        print(f"\n📈 FINAL NODE STATUS:")
        for node, data in WORLD_STATE["nodes"].items():
            icon = "🔧" if data["status"] == "Repairing" else "❌" if data["status"] == "Broken" else "✅"
            print(f"  {icon} {node}: {data['status']} | {data['criticality']} | {data['population_affected']} people")
        
        print(f"\n👷 FINAL CREW STATUS:")
        for crew, data in WORLD_STATE["crews"].items():
            icon = "🛠️" if data["status"] == "Busy" else "✅" if data["status"] == "Available" else "⏸️"
            print(f"  {icon} {crew}: {data['status']} ({data['specialty']})")
        
        # Statistics
        repaired = [n for n, d in WORLD_STATE["nodes"].items() if d["status"] == "Repairing"]
        busy_crews = [c for c, d in WORLD_STATE["crews"].items() if d["status"] == "Busy"]
        
        print(f"\n📊 SUMMARY:")
        print(f"  ✅ Nodes being repaired: {len(repaired)}/{len(initial_broken)} → {repaired}")
        print(f"  🛠️  Busy crews: {len(busy_crews)}/{len(WORLD_STATE['crews'])} → {busy_crews}")
        
        if repaired:
            print(f"\n🎯 SUCCESS: {len(repaired)} repairs initiated!")
        else:
            print(f"\n⚠️  WARNING: No repairs initiated")
        
        # Save run
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(config.runs_path, f"run_{ts}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.memory, f, indent=2)
        print(f"\n💾 Run saved: {path}")

# ==========================================
# 5. MAIN
# ==========================================
if __name__ == "__main__":
    print("🚀 Starting Infrastructure Agent...")
    agent = InfrastructureAgent(max_steps=15)
    agent.run()