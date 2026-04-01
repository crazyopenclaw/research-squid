"""Session, SessionConfig, ResearchModality — session lifecycle objects."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel


class ResearchModality:
    GENERAL = "general"
    LLM_OPTIMIZATION = "llm_optimization"
    DRUG_DISCOVERY = "drug_discovery"
    ENGINEERING_SIMULATION = "engineering_simulation"


class SessionConfig(BaseModel):
    question: str
    modality: str = ResearchModality.GENERAL
    available_backends: List[str] = ["sandbox_python"]
    backend_config: Dict[str, Any] = {}
    llm_budget_usd: float = 20.0
    compute_budget_usd: float = 20.0
    agent_count: int = 10
    user_id: Optional[str] = None


class Session(BaseModel):
    id: str
    question: str
    modality: str
    status: str = "active"
    created_at: datetime = None

    llm_budget_usd: float
    compute_budget_usd: float
    llm_spent_usd: float = 0.0
    compute_spent_usd: float = 0.0

    agent_count: int = 0
    finding_count: int = 0

    def status_summary(self) -> Dict:
        return {
            "session_id": self.id,
            "status": self.status,
            "agents": self.agent_count,
            "findings": self.finding_count,
            "llm_spent": f"${self.llm_spent_usd:.2f} / ${self.llm_budget_usd:.2f}",
            "compute_spent": f"${self.compute_spent_usd:.2f} / ${self.compute_budget_usd:.2f}",
        }
