"""
Virtuals GAME Framework wrapper.
Deploys the Risk Agent as a Virtuals character for the Virtuals track.
"""
import os, requests, json

VIRTUALS_API_KEY = os.getenv("VIRTUALS_API_KEY", "")
VIRTUALS_BASE    = "https://api.virtuals.io/v1"
HEADERS = {"Authorization": f"Bearer {VIRTUALS_API_KEY}", "Content-Type": "application/json"}

RISK_AGENT_PERSONA = """You are the SOLSCOUT Risk Agent — a Solana DeFi risk auditor.
Your job: analyze yield opportunities and flag risks before capital is deployed.
You check: TVL size, audit status, impermanent loss exposure, protocol age, smart contract risk.
You communicate in short, decisive sentences. You are cautious but not paranoid.
When a yield looks safe: "Cleared. Proceed."
When risky: "Hold. [specific risk]. Recommend [alternative]."
"""


def create_risk_agent() -> dict:
    """Create the Risk Agent on Virtuals GAME Framework."""
    if not VIRTUALS_API_KEY:
        return _mock_agent("risk_agent", "Risk Auditor")

    try:
        r = requests.post(f"{VIRTUALS_BASE}/agents", headers=HEADERS, json={
            "name": "SOLSCOUT Risk Agent",
            "description": "Autonomous Solana DeFi risk auditor. Part of the SOLSCOUT yield hunter swarm.",
            "persona": RISK_AGENT_PERSONA,
            "capabilities": ["defi_analysis", "risk_scoring", "protocol_audit"],
            "chain": "solana",
        }, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return _mock_agent("risk_agent", "Risk Auditor", error=str(e))


def get_agent_status(agent_id: str) -> dict:
    """Get Virtuals agent status."""
    if not VIRTUALS_API_KEY or agent_id.startswith("mock_"):
        return {"agent_id": agent_id, "status": "active", "network": "virtuals"}
    try:
        r = requests.get(f"{VIRTUALS_BASE}/agents/{agent_id}", headers=HEADERS, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {"agent_id": agent_id, "status": "unknown"}


def agent_audit(agent_id: str, protocol: str, apy: float, tvl: float, audited: bool) -> dict:
    """Ask the Virtuals Risk Agent to audit a yield opportunity."""
    if not VIRTUALS_API_KEY or agent_id.startswith("mock_"):
        return _mock_audit(protocol, apy, tvl, audited)

    try:
        r = requests.post(f"{VIRTUALS_BASE}/agents/{agent_id}/message", headers=HEADERS, json={
            "message": (
                f"Audit this Solana yield opportunity:\n"
                f"Protocol: {protocol}\nAPY: {apy}%\nTVL: ${tvl:,.0f}\nAudited: {audited}\n"
                f"Should I deploy capital here?"
            )
        }, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception:
        return _mock_audit(protocol, apy, tvl, audited)


def _mock_agent(agent_id: str, role: str, error: str = None) -> dict:
    return {
        "agent_id": f"mock_{agent_id}",
        "name": f"SOLSCOUT {role}",
        "status": "active",
        "network": "virtuals-game",
        "note": error or "Simulated Virtuals agent — deploy with VIRTUALS_API_KEY",
        "virtuals_url": "https://virtuals.io",
    }


def _mock_audit(protocol: str, apy: float, tvl: float, audited: bool) -> dict:
    risk_score = 100
    flags = []
    if apy > 20:
        risk_score -= 30; flags.append("High APY — check reward token sustainability")
    if tvl < 5_000_000:
        risk_score -= 25; flags.append("Low TVL — liquidity risk")
    if not audited:
        risk_score -= 35; flags.append("Unaudited contract — high smart contract risk")

    verdict = "Cleared. Proceed." if risk_score >= 70 else f"Hold. {flags[0]}."
    return {
        "agent_id": "mock_risk_agent",
        "protocol": protocol,
        "risk_score": max(risk_score, 10),
        "flags": flags,
        "verdict": verdict,
        "signed_by": "SOLSCOUT Risk Agent (Virtuals GAME)",
    }
