from typing import Dict, Union, List
from config import WORLD_STATE

def detect_failure_nodes() -> List[str]:
    """
    Scans the infrastructure network to identify nodes that have failed.
    
    Returns:
        List[str]: A list of node IDs that currently have a "Broken" status. 
        Example: ['Node_Water_Pump_A', 'Node_Power_Substation_C']
    """
    return [n for n, d in WORLD_STATE["nodes"].items() if d["status"] == "Broken"]

def estimate_impact(node_id: str) -> Dict[str, Union[str, int]]:
    """
    Calculates the social and functional impact of a specific failed node.
    
    Args:
        node_id (str): The ID of the node to analyze.
        
    Returns:
        Dict: Metrics including population affected and criticality level.
        Example: {'population_affected': 5000, 'criticality': 'High'}
    """
    if node := WORLD_STATE["nodes"].get(node_id):
        return {"node_id": node_id, "type": node["type"], 
                "population_affected": node["population_affected"], "criticality": node["criticality"]}
    return {"error": "Node not found"}

def assign_repair_crew(node_ids: List[str], crew_ids: List[str]) -> Dict[str, str]:
    """
    Assigns available repair crews to broken nodes to initiate repairs.
    
    Args:
        node_ids (List[str]): A list of broken node IDs.
        crew_ids (List[str]): A list of crew IDs to be assigned.
        
    Returns:
        Dict: A report of successful assignments and failures due to crew unavailability.
    """
    results = {}
    for n, c in zip(node_ids, crew_ids):
        if c not in WORLD_STATE["crews"]:
            results[f"{c}->{n}"] = f"Failed (Crew '{c}' not found)"
            continue
        crew_status = WORLD_STATE["crews"][c]["status"]
        if crew_status != "Available":
            results[f"{c}->{n}"] = f"Failed (Crew {crew_status})"
        else:
            WORLD_STATE["nodes"][n]["status"] = "Repairing"
            WORLD_STATE["crews"][c]["status"] = "Busy"  # Το crew γίνεται Busy!
            results[f"{c}->{n}"] = "Success"
            print(f"Crew {c} is now BUSY repairing {n}")
    return results

def check_crew_availability() -> Dict[str, str]:
    """
    Retrieves the current availability status of all repair crews.
    
    Returns:
        Dict: Crew IDs mapped to their current status ('Available' or 'Busy').
    """
    return {c: d["status"] for c, d in WORLD_STATE["crews"].items()}