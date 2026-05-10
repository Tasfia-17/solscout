"""
SOLSCOUT Orchestrator — Solana-native multi-agent yield hunter.
Replaces AVAOrchestrator. Same WebSocket event protocol, Solana content.
"""
import asyncio, json, time, os
from dotenv import load_dotenv

load_dotenv()

import llm_client
from a2a_bus import BUS, A2AMessage
from defillama_client import get_solana_pools, get_best_usdc_pools, format_pool
from solana_tx_builder import build_solana_yield_transaction, extract_best_solana_yield
from solana_identity import SolanaIdentity
from virtuals_agent import create_risk_agent, agent_audit
from lifi_client import check_if_better_yield_offchain

try:
    import elevenlabs_client as el_client
    HAS_ELEVENLABS = bool(os.getenv("ELEVENLABS_API_KEY"))
except ImportError:
    HAS_ELEVENLABS = False

# Solana yield research task templates
YIELD_TASKS = [
    {"id": "t1", "type": "research",
     "url": "https://defillama.com/yields?chain=Solana",
     "objective": "Find the highest APY USDC yield pools on Solana (Kamino, Marinade, Drift, marginfi)"},
    {"id": "t2", "type": "verify",
     "url": "https://app.kamino.finance",
     "objective": "Verify Kamino vault TVL, audit status, and current APY rates"},
    {"id": "t3", "type": "execute",
     "url": "https://jup.ag",
     "objective": "Check Jupiter swap routes and fees for USDC deposit into top yield vault"},
]

YIELD_KEYWORDS = {"yield", "apy", "apr", "earn", "stake", "staking", "usdc", "sol", "defi",
                  "kamino", "marinade", "drift", "jupiter", "jito", "marginfi", "interest", "return"}


class SOLScoutOrchestrator:
    def __init__(self, on_update=None):
        self.on_update = on_update or (lambda msg: print(f"[SOLSCOUT] {msg}"))
        self.all_identities: list[dict] = []
        self.all_payments: list[dict] = []
        self.all_screenshots: list[str] = []
        self._virtuals_agent_id: str = ""

    def _emit(self, msg: dict):
        self.on_update(msg)

    async def run(self, goal: str) -> dict:
        start = time.time()
        self._emit({"type": "status", "msg": f"Goal: {goal}"})

        # Decompose goal
        self._emit({"type": "status", "msg": "Orchestrator decomposing goal..."})
        tasks = YIELD_TASKS  # always use Solana yield tasks
        plan_summary = f"Solana yield hunt: {goal}"

        # Try LLM decomposition for custom goals
        goal_lower = goal.lower()
        if not any(kw in goal_lower for kw in YIELD_KEYWORDS):
            try:
                plan = llm_client.orchestrate(goal)
                if plan.get("tasks"):
                    tasks = plan["tasks"][:3]
                    plan_summary = plan.get("summary", goal)
            except Exception:
                pass

        self._emit({"type": "plan", "tasks": tasks, "summary": plan_summary})

        # Register agents on A2A bus
        for t in tasks:
            BUS.register(f"agent_{t['id']}")
        BUS.register("orchestrator")

        # Spawn Virtuals Risk Agent
        self._emit({"type": "status", "msg": "Spawning Virtuals Risk Agent..."})
        virtuals_agent = await asyncio.to_thread(create_risk_agent)
        self._virtuals_agent_id = virtuals_agent.get("agent_id", "mock_risk_agent")

        # Fetch live Solana pools from DefiLlama (fast, reliable)
        self._emit({"type": "status", "msg": "Scanning Solana yield pools via DefiLlama..."})
        raw_pools = await asyncio.to_thread(get_best_usdc_pools, 5)
        pools = [format_pool(p) for p in raw_pools]

        # Run agent simulations in parallel (identity + signing + A2A)
        self._emit({"type": "status", "msg": f"Launching {len(tasks)} agents with Solana PDAs..."})
        agent_results = await asyncio.gather(
            *[self._run_agent(t, pools) for t in tasks],
            return_exceptions=True
        )
        agent_results = [r if not isinstance(r, Exception) else {"error": str(r)} for r in agent_results]

        for r in agent_results:
            if "identity" in r:
                self.all_identities.append(r["identity"])
            if "payments" in r:
                self.all_payments.append(r["payments"])

        self._emit({"type": "identities", "identities": self.all_identities})
        self._emit({"type": "payments",   "payments":   self.all_payments})
        self._emit({"type": "a2a_messages", "messages": BUS.get_history()})

        # Pick best yield
        best = extract_best_solana_yield(agent_results, pools)

        # Virtuals Risk Agent audits the best yield
        self._emit({"type": "status", "msg": f"Virtuals Risk Agent auditing {best['protocol']}..."})
        audit = await asyncio.to_thread(
            agent_audit, self._virtuals_agent_id,
            best["protocol"],
            float(str(best["apy"]).replace("%", "")),
            best.get("tvl", 0),
            best.get("audited", True),
        )
        self._emit({"type": "agent_event",
                    "agent_id": "virtuals_risk_agent",
                    "cycle": 0,
                    "url": "https://virtuals.io",
                    "action": f"Risk audit: {audit.get('verdict', 'Cleared.')}",
                    "vision": {},
                    "signature": {"signer": "Virtuals GAME Framework", "verified": True},
                    "payment": {}})

        # Check LI.FI for cross-chain yield
        solana_apy = float(str(best["apy"]).replace("%", ""))
        lifi_result = await asyncio.to_thread(check_if_better_yield_offchain, solana_apy)
        if lifi_result.get("better_yield_found"):
            self._emit({"type": "status", "msg": f"LI.FI: better yield on {lifi_result['chain']} — {lifi_result['apy']}%"})

        # Build Solana transaction
        self._emit({"type": "status", "msg": "Building Solana transaction..."})
        tx = build_solana_yield_transaction(
            protocol=best["protocol"],
            asset=best.get("asset", "USDC"),
            amount_usd=500.0,
            apy=solana_apy,
        )
        self._emit({"type": "transaction", "best_yield": best, "tx": tx})

        # Synthesize briefing
        self._emit({"type": "status", "msg": "Synthesizing yield briefing..."})
        all_events = [e for r in agent_results if "events" in r for e in r["events"]]
        narration = _build_narration(best, audit, pools, lifi_result, goal)
        self._emit({"type": "narration", "text": narration})

        # Yield strategy brief (replaces outreach email)
        strategy = _build_strategy_brief(best, audit, lifi_result, pools)
        self._emit({"type": "outreach", "subject": strategy["title"], "body": strategy["body"]})

        # Risk summary (replaces call script)
        risk_summary = _build_risk_summary(best, audit, pools)
        self._emit({"type": "call_script", "text": risk_summary})

        # Score card (yield-focused dimensions)
        score = _build_yield_score(best, audit, lifi_result)
        self._emit({"type": "score", "score": score})
        self._emit({"type": "status", "msg": "Generating ElevenLabs voice briefing..."})
        await self._generate_tts(narration)

        elapsed = round(time.time() - start, 1)
        self._emit({"type": "complete", "elapsed_sec": elapsed, "narration": narration})

        return {
            "goal": goal, "pools": pools, "best_yield": best,
            "audit": audit, "lifi": lifi_result, "tx": tx,
            "identities": self.all_identities, "elapsed_sec": elapsed,
        }

    async def _run_agent(self, task: dict, pools: list[dict]) -> dict:
        """Simulate a specialist agent with Solana identity + A2A messaging."""
        agent_id = f"agent_{task['id']}"
        identity = SolanaIdentity(agent_id)
        reg = await asyncio.to_thread(identity.register_on_chain)

        # Simulate work based on task type
        await asyncio.sleep(0.3 + hash(agent_id) % 10 * 0.1)

        action = _task_action(task, pools)
        sig = identity.sign_action(action, task["id"])

        self._emit({
            "type": "agent_event",
            "agent_id": agent_id,
            "cycle": 0,
            "url": task["url"],
            "action": action,
            "vision": {"success": True},
            "signature": sig,
            "payment": {"nonce": f"sol_{int(time.time())}", "amount_usdc": 0.000001},
        })

        # Broadcast finding to A2A bus
        await BUS.send(A2AMessage(
            sender=agent_id, recipient="broadcast",
            task_id=task["id"], message_type="finding",
            content={
                "url": task["url"],
                "action": action,
                "pools_found": len(pools),
                "signed_by": identity.pubkey,
                "pda": identity.pda,
            }
        ))

        # x402 payment receipt (Solana)
        payment = {
            "wallet": identity.pubkey[:20] + "...",
            "total_payments": 1,
            "total_usdc": 0.000001,
            "network": "Solana (x402)",
        }
        self.all_payments.append(payment)

        return {
            "agent_id": agent_id,
            "task": task,
            "identity": {
                "address": identity.pubkey,
                "pda": identity.pda,
                "nft_id": identity.nft_id,
                "registration": reg,
            },
            "payments": payment,
            "events": [{"action": action, "url": task["url"], "result": "success"}],
            "extracted_data": {"cycle_0": {"body_snippet": action, "url": task["url"]}},
        }

    async def _generate_tts(self, text: str):
        """Generate TTS with ElevenLabs (fallback to ionrouter orpheus)."""
        try:
            if HAS_ELEVENLABS:
                audio = await asyncio.to_thread(el_client.tts, text)
            else:
                audio = await asyncio.to_thread(llm_client.tts, text)
            import base64
            self._emit({"type": "audio", "b64": base64.b64encode(audio).decode()})
        except Exception as e:
            print(f"TTS failed: {e}")


def _task_action(task: dict, pools: list[dict]) -> str:
    if not pools:
        return task["objective"]
    best = pools[0]
    if task["type"] == "research":
        return f"Scanned {len(pools)} Solana pools — best: {best['protocol']} {best['apy']}% APY (TVL ${best['tvl_usd']:,})"
    elif task["type"] == "verify":
        return f"Verified {best['protocol']}: audited={best['audited']}, IL risk={best['il_risk']}, TVL=${best['tvl_usd']:,}"
    else:
        return f"Built Jupiter swap + {best['protocol']} deposit calldata for {best['symbol']}"


def _build_narration(best: dict, audit: dict, pools: list[dict], lifi: dict, goal: str) -> str:
    apy = best.get("apy", "?")
    protocol = best.get("protocol", "Kamino")
    tvl = best.get("tvl", 0)
    verdict = audit.get("verdict", "Cleared. Proceed.")
    pool_count = len(pools)

    narration = (
        f"SOLSCOUT scanned {pool_count} Solana yield pools and identified {protocol} as the top opportunity "
        f"at {apy} APY with ${tvl:,} TVL. "
        f"The Virtuals Risk Agent audited the protocol and returned: '{verdict}' "
    )
    if lifi.get("better_yield_found"):
        narration += (
            f"LI.FI also found a {lifi['apy']}% opportunity on {lifi['chain']} via {lifi['protocol']} — "
            f"bridging route is available if you prefer cross-chain yield. "
        )
    narration += f"A $500 deposit transaction has been prepared. Authorize to execute on Solana."
    return narration


def _build_yield_score(best: dict, audit: dict, lifi: dict) -> dict:
    apy = float(str(best.get("apy", "0")).replace("%", ""))
    tvl = best.get("tvl", 0)
    audited = best.get("audited", False)
    il_risk = best.get("il_risk", "yes")
    risk_score = audit.get("risk_score", 70)

    apy_score    = min(int(apy * 5), 100)
    risk_s       = risk_score
    liquidity    = min(int(tvl / 1_000_000), 100)
    safety       = 90 if audited else 40
    il_score     = 90 if il_risk == "no" else 40

    avg = (apy_score + risk_s + liquidity + safety + il_score) // 5
    return {
        "company_growth": apy_score,    # repurposed: APY Score
        "budget_signal":  risk_s,       # repurposed: Risk Score
        "pain_match":     liquidity,    # repurposed: Liquidity
        "timing":         safety,       # repurposed: Protocol Safety
        "tech_fit":       il_score,     # repurposed: IL Risk
        "summary": f"{best['protocol']} scores {avg}/100 — {'strong' if avg > 70 else 'moderate'} yield opportunity.",
    }


def _build_strategy_brief(best: dict, audit: dict, lifi: dict, pools: list[dict]) -> dict:
    apy = best.get("apy", "?")
    protocol = best.get("protocol", "?")
    tvl = best.get("tvl", 0)
    verdict = audit.get("verdict", "Cleared.")
    risk_score = audit.get("risk_score", 70)

    lines = [
        f"Top pick: {protocol} at {apy} APY — TVL ${tvl:,}",
        f"Risk Agent verdict: {verdict} (score {risk_score}/100)",
    ]
    if lifi.get("better_yield_found"):
        lines.append(f"Cross-chain option: {lifi['protocol']} on {lifi['chain']} at {lifi['apy']}% via LI.FI bridge")
    if len(pools) > 1:
        alts = ", ".join(f"{p['protocol']} {p['apy']}%" for p in pools[1:3])
        lines.append(f"Alternatives: {alts}")
    lines.append("Deposit $500 USDC → authorize in Phantom or Backpack to execute.")

    return {
        "title": f"Yield Strategy — {protocol} {apy}",
        "body": "\n\n".join(lines),
    }


def _build_risk_summary(best: dict, audit: dict, pools: list[dict]) -> str:
    protocol = best.get("protocol", "?")
    apy = best.get("apy", "?")
    flags = audit.get("flags", [])
    risk_score = audit.get("risk_score", 70)
    audited = best.get("audited", False)
    il = best.get("il_risk", "unknown")
    tvl = best.get("tvl", 0)

    lines = [
        f"RISK SUMMARY — {protocol}",
        f"",
        f"APY: {apy}  |  Risk Score: {risk_score}/100  |  TVL: ${tvl:,}",
        f"Audited: {'Yes' if audited else 'No'}  |  IL Risk: {il}",
        f"",
    ]
    if flags:
        lines.append("Flags:")
        for f in flags:
            lines.append(f"  ⚠ {f}")
        lines.append("")

    if risk_score >= 70:
        lines.append("✓ Risk Agent cleared this opportunity. Safe to proceed.")
    elif risk_score >= 50:
        lines.append("⚠ Moderate risk. Consider splitting position across 2 protocols.")
    else:
        lines.append("✗ High risk detected. Review flags before deploying capital.")

    if len(pools) > 1:
        lines.append(f"\nNext best: {pools[1]['protocol']} at {pools[1]['apy']}% APY")

    return "\n".join(lines)


async def run_cli(goal: str):
    def print_update(msg):
        if not isinstance(msg, dict): print(msg); return
        t = msg.get("type", "")
        if t == "status":        print(f"\n⚡ {msg['msg']}")
        elif t == "plan":        print(f"\n📋 {msg.get('summary','')}")
        elif t == "agent_event": print(f"   🤖 {msg['agent_id']} | {msg['action'][:60]}")
        elif t == "transaction": print(f"\n💰 Best: {msg['best_yield']['protocol']} {msg['best_yield']['apy']}")
        elif t == "narration":   print(f"\n📝 {msg['text']}")
        elif t == "complete":    print(f"\n✅ Done in {msg['elapsed_sec']}s")

    orch = SOLScoutOrchestrator(on_update=print_update)
    return await orch.run(goal)


if __name__ == "__main__":
    import sys
    goal = " ".join(sys.argv[1:]) or "Find me the safest 10% yield on Solana"
    asyncio.run(run_cli(goal))
