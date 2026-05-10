"""
Solana transaction builder — Jupiter swap + Kamino/Marinade deposit.
Uses Jupiter Quote API (free, no key needed) + static deposit calldata.
Replaces Aave V3 / Base Sepolia tx_builder.py
"""
import requests, json

JUPITER_QUOTE  = "https://quote-api.jup.ag/v6/quote"
JUPITER_SWAP   = "https://quote-api.jup.ag/v6/swap"

# Solana token mints
USDC_MINT  = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
SOL_MINT   = "So11111111111111111111111111111111111111112"
MSOL_MINT  = "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So"
JITOSOL_MINT = "J1toso1uCk3RLmjorhTtrVwY9HJ7X8V9yYac6Y7kGCPn"

# Kamino USDC vault (JLP strategy)
KAMINO_USDC_VAULT = "DdFPRnccQqLD4zCHrBqdAJpRmUpatEPZnR9jYGDmEtB2"
# Marinade staking program
MARINADE_PROGRAM  = "MarBmsSgKXdrN1egZf5sqe1TMai9K1rChYNDJgjq7aD"


def get_jupiter_quote(input_mint: str, output_mint: str, amount_lamports: int) -> dict:
    """Get best swap route from Jupiter."""
    try:
        r = requests.get(JUPITER_QUOTE, params={
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": amount_lamports,
            "slippageBps": 50,
        }, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def build_solana_yield_transaction(
    protocol: str,
    asset: str,
    amount_usd: float,
    apy: float,
    user_address: str = "11111111111111111111111111111111"
) -> dict:
    """
    Build a Solana yield deposit transaction preview.
    Returns human-readable steps + Jupiter quote if applicable.
    """
    amount_lamports = int(amount_usd * 1_000_000)  # USDC 6 decimals
    protocol_lower = protocol.lower()

    steps = []
    jupiter_quote = None

    if "kamino" in protocol_lower:
        # Jupiter USDC → JLP, then Kamino deposit
        jupiter_quote = get_jupiter_quote(USDC_MINT, USDC_MINT, amount_lamports)
        steps = [
            {
                "step": 1,
                "description": f"Approve {amount_usd} USDC for Kamino vault",
                "program": "Token Program",
                "account": USDC_MINT,
                "data": f"approve {amount_lamports} lamports",
            },
            {
                "step": 2,
                "description": f"Deposit {amount_usd} USDC into Kamino JLP vault ({apy}% APY)",
                "program": "Kamino Finance",
                "account": KAMINO_USDC_VAULT,
                "data": f"deposit {amount_lamports}",
            },
        ]
        note = f"Estimated yield: ${amount_usd * apy / 100 / 365:.4f}/day"

    elif "marinade" in protocol_lower or "msol" in asset.lower():
        # SOL → mSOL via Marinade
        sol_amount = int(amount_usd * 1_000_000_000 / 150)  # rough SOL price
        steps = [
            {
                "step": 1,
                "description": f"Stake {amount_usd:.2f} USDC worth of SOL with Marinade",
                "program": "Marinade Finance",
                "account": MARINADE_PROGRAM,
                "data": f"deposit {sol_amount} lamports",
            },
            {
                "step": 2,
                "description": f"Receive mSOL tokens ({apy}% APY, auto-compounding)",
                "program": "Token Program",
                "account": MSOL_MINT,
                "data": "mint mSOL",
            },
        ]
        note = "mSOL auto-compounds — no claiming needed"

    elif "jito" in protocol_lower:
        steps = [
            {
                "step": 1,
                "description": f"Stake SOL with Jito for JitoSOL ({apy}% APY + MEV rewards)",
                "program": "Jito Stake Pool",
                "account": JITOSOL_MINT,
                "data": f"deposit_sol {int(amount_usd * 1e9 / 150)}",
            },
        ]
        note = "JitoSOL includes MEV tip rewards on top of base staking yield"

    elif "drift" in protocol_lower:
        steps = [
            {
                "step": 1,
                "description": f"Deposit {amount_usd} USDC into Drift lending pool ({apy}% APY)",
                "program": "Drift Protocol",
                "account": "dRiftyHA39MWEi3m9aunc5MzRF1JYuBsbn6VPcn33UH",
                "data": f"deposit {amount_lamports} USDC",
            },
        ]
        note = "Drift lending — withdraw anytime, no lockup"

    else:  # marginfi / generic
        steps = [
            {
                "step": 1,
                "description": f"Deposit {amount_usd} USDC into {protocol} ({apy}% APY)",
                "program": protocol,
                "account": user_address,
                "data": f"deposit {amount_lamports}",
            },
        ]
        note = f"Connect Phantom or Backpack wallet to sign"

    result = {
        "status": "ready",
        "protocol": protocol,
        "action": f"Deposit {amount_usd} USDC",
        "apy": f"{apy}%",
        "chain": "Solana",
        "network": "mainnet-beta",
        "steps": steps,
        "note": note,
        "solscan_preview": f"https://solscan.io/account/{KAMINO_USDC_VAULT}",
    }

    if jupiter_quote and "error" not in jupiter_quote:
        result["jupiter_route"] = {
            "in_amount": jupiter_quote.get("inAmount"),
            "out_amount": jupiter_quote.get("outAmount"),
            "price_impact": jupiter_quote.get("priceImpactPct"),
            "route_plan": [r.get("swapInfo", {}).get("label", "") for r in jupiter_quote.get("routePlan", [])[:3]],
        }

    return result


def extract_best_solana_yield(agent_results: list[dict], pools: list[dict] = None) -> dict:
    """Pick the best yield from agent results or DefiLlama pools."""
    import llm_client, re

    # If we have live DefiLlama pools, use the top one
    if pools:
        best = pools[0]
        return {
            "protocol": best.get("protocol", "Kamino"),
            "apy": f"{best.get('apy', 0):.1f}%",
            "asset": best.get("symbol", "USDC"),
            "tvl": best.get("tvl_usd", 0),
            "il_risk": best.get("il_risk", "no"),
            "audited": best.get("audited", True),
            "confidence": "high",
        }

    # Fallback: parse agent text
    all_text = ""
    for r in agent_results:
        for cycle_data in r.get("extracted_data", {}).values():
            all_text += cycle_data.get("body_snippet", "") + "\n"

    if not all_text.strip():
        return {"protocol": "Kamino", "apy": "11.2%", "asset": "USDC", "tvl": 45_000_000,
                "il_risk": "no", "audited": True, "confidence": "medium"}

    resp = llm_client.chat([{
        "role": "user",
        "content": (
            f"From this Solana DeFi research, extract the best yield opportunity.\n"
            f"Data: {all_text[:1500]}\n"
            f"Reply ONLY with JSON: {{\"protocol\":\"name\",\"apy\":\"X.X%\",\"asset\":\"USDC\","
            f"\"tvl\":0,\"il_risk\":\"no\",\"audited\":true,\"confidence\":\"high/medium/low\"}}"
        )
    }], model="qwen3-8b", max_tokens=100)

    import re
    content = re.sub(r'<think>.*?</think>', '', resp.content or "", flags=re.DOTALL)
    match = re.search(r'\{.*\}', content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass

    return {"protocol": "Kamino", "apy": "11.2%", "asset": "USDC", "tvl": 45_000_000,
            "il_risk": "no", "audited": True, "confidence": "medium"}
