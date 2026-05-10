"""
FastAPI server — WebSocket-based real-time dashboard for AVA.
"""
import asyncio, json, os, base64
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()

from solscout_orchestrator import SOLScoutOrchestrator

app = FastAPI(title="SCOUT — AI Sales Intelligence")
app.mount("/static", StaticFiles(directory="static"), name="static")

connections: list[WebSocket] = []
last_result: dict = {}
autonomous_task = None  # background watcher task


async def broadcast(msg: dict):
    dead = []
    for ws in connections:
        try:
            await ws.send_json(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        connections.remove(ws)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    connections.append(ws)
    if last_result:
        await ws.send_json({"type": "history", "data": last_result})
    # Send autonomous mode status
    await ws.send_json({"type": "auto_status", "active": autonomous_task is not None and not autonomous_task.done()})
    try:
        while True:
            data = await ws.receive_json()
            if data.get("type") == "run":
                goal = data.get("goal", "").strip()
                if not goal:
                    await ws.send_json({"type": "error", "msg": "Empty goal"})
                    continue
                asyncio.create_task(_run_goal(goal))
            elif data.get("type") == "auto_start":
                await _start_autonomous()
            elif data.get("type") == "auto_stop":
                await _stop_autonomous()
            elif data.get("type") == "queue_add":
                await _add_to_queue(data.get("prospect", ""))
    except WebSocketDisconnect:
        connections.remove(ws)


async def _run_goal(goal: str):
    global last_result

    async def on_update(msg):
        await broadcast(msg)
        if isinstance(msg, dict) and msg.get("type") == "briefing":
            b = msg.get("briefing", {})
            # Stream storyboard frames
            for i, img in enumerate(b.get("images", [])):
                await broadcast({"type": "storyboard_frame", "index": i, "b64": img["b64"], "prompt": img.get("prompt","")})
            # Stream audio
            if b.get("audio_b64"):
                await broadcast({"type": "audio", "b64": b["audio_b64"]})

    def sync_update(msg):
        asyncio.create_task(on_update(msg))

    orch = SOLScoutOrchestrator(on_update=sync_update)
    result = await orch.run(goal)
    last_result = result

    # Send screenshots (if any)
    for i, b64 in enumerate(getattr(orch, 'all_screenshots', [])[:6]):
        await broadcast({"type": "screenshot", "index": i, "b64": b64})


@app.get("/")
async def index():
    return FileResponse("static/index.html")


@app.get("/health")
async def health():
    return {"status": "ok"}


async def _start_autonomous():
    global autonomous_task
    from watcher import watch_queue
    if autonomous_task and not autonomous_task.done():
        return
    await broadcast({"type": "auto_status", "active": True})
    await broadcast({"type": "status", "msg": "Autonomous mode active — watching prospects.csv"})

    async def on_prospect(goal: str):
        await broadcast({"type": "status", "msg": f"[AUTO] New prospect: {goal}"})
        await _run_goal(goal)

    autonomous_task = asyncio.create_task(watch_queue(on_prospect))


async def _stop_autonomous():
    global autonomous_task
    if autonomous_task:
        autonomous_task.cancel()
        autonomous_task = None
    await broadcast({"type": "auto_status", "active": False})
    await broadcast({"type": "status", "msg": "Autonomous mode stopped"})


async def _add_to_queue(prospect: str):
    """Add a prospect to the CSV queue from the dashboard."""
    if not prospect.strip():
        return
    import csv
    from pathlib import Path
    queue_file = Path("prospects.csv")
    rows = []
    if queue_file.exists():
        with open(queue_file, newline="") as f:
            rows = list(csv.DictReader(f))
    new_id = str(max((int(r.get("id",0)) for r in rows), default=0) + 1)
    rows.append({"id": new_id, "prospect": prospect, "status": "pending"})
    with open(queue_file, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id","prospect","status"])
        w.writeheader()
        w.writerows(rows)
    await broadcast({"type": "status", "msg": f"Added to queue: {prospect}"})


@app.post("/demo")
async def demo_mode():
    """Fire pre-cached demo events so the demo never breaks live."""
    import asyncio
    asyncio.create_task(_run_demo())
    return {"status": "started"}


async def _run_demo():
    import asyncio
    events = [
        {"type": "status", "msg": "Goal: Find me the safest 10% yield on Solana"},
        {"type": "plan", "summary": "Scan Solana yield pools, audit risk, build deposit transaction", "tasks": [
            {"id": "t1", "type": "research", "url": "https://defillama.com/yields?chain=Solana", "objective": "Scan Kamino, Marinade, Drift, marginfi for best USDC APY"},
            {"id": "t2", "type": "verify",   "url": "https://app.kamino.finance",                "objective": "Verify Kamino vault TVL, audit status, and current APY"},
            {"id": "t3", "type": "execute",  "url": "https://jup.ag",                            "objective": "Build Jupiter swap + Kamino deposit calldata"},
        ]},
        {"type": "status", "msg": "Launching 3 agents with Solana PDAs..."},
        {"type": "agent_event", "agent_id": "agent_t1", "cycle": 0, "url": "https://defillama.com/yields?chain=Solana",
         "action": "Scanned 47 Solana pools — best: Kamino 11.2% APY (TVL $45,000,000)",
         "vision": {}, "signature": {"signer": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU", "verified": True, "network": "devnet"}, "payment": {"nonce": "sol_1715305557"}},
        {"type": "agent_event", "agent_id": "agent_t2", "cycle": 0, "url": "https://app.kamino.finance",
         "action": "Verified Kamino: audited=True, IL risk=no, TVL=$45,000,000",
         "vision": {}, "signature": {"signer": "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM", "verified": True, "network": "devnet"}, "payment": {"nonce": "sol_1715305558"}},
        {"type": "agent_event", "agent_id": "virtuals_risk_agent", "cycle": 0, "url": "https://virtuals.io",
         "action": "Risk audit: Cleared. Proceed. — Kamino scores 87/100 risk score",
         "vision": {}, "signature": {"signer": "Virtuals GAME Framework", "verified": True}, "payment": {}},
        {"type": "agent_event", "agent_id": "agent_t3", "cycle": 0, "url": "https://jup.ag",
         "action": "Built Jupiter swap + Kamino JLP vault deposit calldata for USDC",
         "vision": {}, "signature": {"signer": "BvmmEBZJqLhSMaFNsGFMbKKqFcjZSiMnMHGHGHGHGHGH", "verified": True, "network": "devnet"}, "payment": {"nonce": "sol_1715305560"}},
        {"type": "identities", "identities": [
            {"address": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU", "pda": "kamino-scout-pda-4821", "nft_id": 4821, "registration": {"status": "simulated", "network": "devnet", "solscan_url": "https://solscan.io/account/7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU?cluster=devnet"}},
            {"address": "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM", "pda": "kamino-risk-pda-4822",  "nft_id": 4822, "registration": {"status": "simulated", "network": "devnet", "solscan_url": "https://solscan.io/account/9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM?cluster=devnet"}},
            {"address": "BvmmEBZJqLhSMaFNsGFMbKKqFcjZSiMnMHGHGHGHGHGH", "pda": "kamino-exec-pda-4823",  "nft_id": 4823, "registration": {"status": "simulated", "network": "devnet", "solscan_url": "https://solscan.io/account/BvmmEBZJqLhSMaFNsGFMbKKqFcjZSiMnMHGHGHGHGHGH?cluster=devnet"}},
        ]},
        {"type": "a2a_messages", "messages": [
            {"sender": "agent_t1", "recipient": "broadcast",  "type": "finding", "content": {"url": "defillama.com", "snippet": "Kamino JLP vault: 11.2% APY, $45M TVL, audited by OtterSec. Top pick."}, "ts": 0},
            {"sender": "agent_t2", "recipient": "broadcast",  "type": "finding", "content": {"url": "kamino.finance", "snippet": "Verified: contract audited, no IL risk, TVL stable last 30 days."}, "ts": 0},
            {"sender": "agent_t3", "recipient": "agent_t1",   "type": "finding", "content": {"url": "jup.ag",         "snippet": "Jupiter route ready: USDC → JLP, 0.05% fee, 2.4s confirmation."}, "ts": 0},
        ]},
        {"type": "payments", "payments": [
            {"wallet": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU", "total_payments": 3, "total_usdc": 0.000003, "network": "Solana (x402)"},
        ]},
        {"type": "transaction", "best_yield": {
            "protocol": "Kamino", "apy": "11.2%", "asset": "USDC",
            "tvl": 45_000_000, "il_risk": "no", "audited": True, "confidence": "high"
        }, "tx": {
            "status": "ready", "protocol": "Kamino", "action": "Deposit 500 USDC",
            "apy": "11.2%", "chain": "Solana", "network": "mainnet-beta",
            "steps": [
                {"step": 1, "description": "Approve 500 USDC for Kamino vault", "program": "Token Program", "account": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", "data": "approve 500000000 lamports"},
                {"step": 2, "description": "Deposit 500 USDC into Kamino JLP vault (11.2% APY)", "program": "Kamino Finance", "account": "DdFPRnccQqLD4zCHrBqdAJpRmUpatEPZnR9jYGDmEtB2", "data": "deposit 500000000"},
            ],
            "note": "Estimated yield: $0.1534/day · Connect Phantom to sign",
            "solscan_preview": "https://solscan.io/account/DdFPRnccQqLD4zCHrBqdAJpRmUpatEPZnR9jYGDmEtB2",
        }},
        {"type": "narration", "text": "SOLSCOUT scanned 47 Solana yield pools and identified Kamino as the top opportunity at 11.2% APY with $45,000,000 TVL. The Virtuals Risk Agent audited the protocol and returned: 'Cleared. Proceed.' — Kamino scores 87/100 on risk. A $500 deposit transaction has been prepared. Authorize to execute on Solana."},
        {"type": "outreach", "subject": "Yield Strategy — Kamino 11.2%", "body": "Top pick: Kamino at 11.2% APY — TVL $45,000,000\n\nRisk Agent verdict: Cleared. Proceed. (score 87/100)\n\nAlternatives: Marinade-Liquid-Staking 6.87%, Drift-Staked-Sol 6.47%\n\nDeposit $500 USDC → authorize in Phantom or Backpack to execute."},
        {"type": "call_script", "text": "RISK SUMMARY — Kamino\n\nAPY: 11.2%  |  Risk Score: 87/100  |  TVL: $45,000,000\nAudited: Yes  |  IL Risk: no\n\n✓ Risk Agent cleared this opportunity. Safe to proceed.\n\nNext best: Marinade-Liquid-Staking at 6.87% APY"},
        {"type": "score", "score": {"company_growth": 56, "budget_signal": 87, "pain_match": 45, "timing": 90, "tech_fit": 90, "summary": "Kamino scores 73/100 — strong yield opportunity with low risk."}},
        {"type": "complete", "elapsed_sec": 8},
    ]
    for event in events:
        await broadcast(event)
        await asyncio.sleep(1.0)


@app.get("/seedance/{task_id}")
async def seedance_poll(task_id: str):
    from video_briefing import poll_seedance
    return poll_seedance(task_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
