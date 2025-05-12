import os
import json
import time
import datetime
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, asdict, field

@dataclass
class Incident:
    """Represents an incident detected by the agent"""
    id: str
    type: str  # "cpu" or "memory"
    pod_name: str
    namespace: str
    timestamp: int
    severity: str  # "low", "medium", "high"
    metrics: Dict[str, Any]
    action_taken: Optional[str] = None
    github_issue: Optional[Dict[str, Any]] = None
    github_pr: Optional[Dict[str, Any]] = None
    resolved: bool = False
    resolved_timestamp: Optional[int] = None
    notes: Optional[str] = None

class IncidentStore:
    """Store for tracking incidents and restart counts"""
    
    def __init__(self, data_file: str = "incidents.json"):
        """Initialize incident store with data file path"""
        self.data_file = data_file
        self.incidents: List[Incident] = []
        self.restart_counts: Dict[str, Dict[str, int]] = {}  # {date: {pod_name: count}}
        self.load()
    
    def load(self):
        """Load incidents and restart counts from data file"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r") as f:
                    data = json.load(f)
                    
                    # Load incidents
                    self.incidents = [Incident(**incident) for incident in data.get("incidents", [])]
                    
                    # Load restart counts
                    self.restart_counts = data.get("restart_counts", {})
            except Exception as e:
                print(f"Error loading incident data: {e}")
    
    def save(self):
        """Save incidents and restart counts to data file"""
        try:
            data = {
                "incidents": [asdict(incident) for incident in self.incidents],
                "restart_counts": self.restart_counts
            }
            
            with open(self.data_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving incident data: {e}")
    
    def add_incident(self, incident: Incident) -> Incident:
        """Add a new incident"""
        self.incidents.append(incident)
        self.save()
        return incident
    
    def get_incident(self, incident_id: str) -> Optional[Incident]:
        """Get an incident by ID"""
        for incident in self.incidents:
            if incident.id == incident_id:
                return incident
        return None
    
    def update_incident(self, incident_id: str, **kwargs) -> Optional[Incident]:
        """Update an incident"""
        incident = self.get_incident(incident_id)
        if incident:
            for key, value in kwargs.items():
                if hasattr(incident, key):
                    setattr(incident, key, value)
            self.save()
            return incident
        return None
    
    def resolve_incident(self, incident_id: str, notes: Optional[str] = None) -> Optional[Incident]:
        """Resolve an incident"""
        incident = self.get_incident(incident_id)
        if incident:
            incident.resolved = True
            incident.resolved_timestamp = int(time.time())
            if notes:
                incident.notes = notes
            self.save()
            return incident
        return None
    
    def get_incidents(self, 
                     resolved: Optional[bool] = None, 
                     incident_type: Optional[str] = None,
                     pod_name: Optional[str] = None,
                     namespace: Optional[str] = None,
                     since: Optional[int] = None,
                     limit: Optional[int] = None) -> List[Incident]:
        """Get incidents with optional filtering"""
        filtered = self.incidents
        
        if resolved is not None:
            filtered = [i for i in filtered if i.resolved == resolved]
        
        if incident_type:
            filtered = [i for i in filtered if i.type == incident_type]
        
        if pod_name:
            filtered = [i for i in filtered if i.pod_name == pod_name]
        
        if namespace:
            filtered = [i for i in filtered if i.namespace == namespace]
        
        if since:
            filtered = [i for i in filtered if i.timestamp >= since]
        
        # Sort by timestamp (newest first)
        filtered = sorted(filtered, key=lambda i: i.timestamp, reverse=True)
        
        if limit:
            filtered = filtered[:limit]
        
        return filtered
    
    def increment_restart_count(self, pod_name: str, namespace: str) -> int:
        """Increment restart count for a pod on the current date"""
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        
        if today not in self.restart_counts:
            self.restart_counts[today] = {}
        
        pod_key = f"{namespace}/{pod_name}"
        
        if pod_key not in self.restart_counts[today]:
            self.restart_counts[today][pod_key] = 0
        
        self.restart_counts[today][pod_key] += 1
        self.save()
        
        return self.restart_counts[today][pod_key]
    
    def get_restart_count(self, pod_name: str, namespace: str) -> int:
        """Get restart count for a pod on the current date"""
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        
        if today not in self.restart_counts:
            return 0
        
        pod_key = f"{namespace}/{pod_name}"
        
        if pod_key not in self.restart_counts[today]:
            return 0
        
        return self.restart_counts[today][pod_key]
    
    def get_all_restart_counts(self) -> Dict[str, Dict[str, int]]:
        """Get all restart counts"""
        return self.restart_counts
    
    def clear_old_restart_counts(self, days_to_keep: int = 7):
        """Clear restart counts older than specified days"""
        today = datetime.datetime.now().date()
        
        dates_to_remove = []
        for date_str in self.restart_counts:
            try:
                date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
                days_old = (today - date).days
                
                if days_old > days_to_keep:
                    dates_to_remove.append(date_str)
            except ValueError:
                # Invalid date format, remove it
                dates_to_remove.append(date_str)
        
        for date_str in dates_to_remove:
            del self.restart_counts[date_str]
        
        if dates_to_remove:
            self.save()

# Create a global instance of the incident store
incident_store = IncidentStore()
