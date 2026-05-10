"""
LI.FI cross-chain route fetcher.
If best yield is on another chain, LI.FI bridges USDC from Solana invisibly.
"""
import requests

LIFI_QUOTE = "https://li.quest/v1/quote"
LIFI_CHAINS = "https://li.quest/v1/chains"

# Chain IDs
SOLANA_CHAIN_ID = "SOL"
BASE_CHAIN_ID   = "8453"
ETH_CHAIN_ID    = "1"

USDC_SOLANA = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDC_BASE   = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
USDC_ETH    = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"


def get_cross_chain_route(
    from_chain: str,
    to_chain: str,
    from_token: str,
    to_token: str,
    amount_usd: float,
    from_address: str = "11111111111111111111111111111111",
) -> dict:
    """Get a LI.FI cross-chain swap/bridge route."""
    amount_atomic = int(amount_usd * 1_000_000)  # USDC 6 decimals
    try:
        r = requests.get(LIFI_QUOTE, params={
            "fromChain": from_chain,
            "toChain": to_chain,
            "fromToken": from_token,
            "toToken": to_token,
            "fromAmount": amount_atomic,
            "fromAddress": from_address,
        }, timeout=12)
        r.raise_for_status()
        data = r.json()
        return _format_route(data, amount_usd)
    except Exception as e:
        return _fallback_route(from_chain, to_chain, amount_usd, str(e))


def check_if_better_yield_offchain(solana_apy: float) -> dict:
    """
    Check if a better yield exists on Base/Ethereum via LI.FI.
    Returns route if cross-chain yield is meaningfully better (>2% delta).
    """
    # Hardcoded reference yields for demo (in production: query DefiLlama for Base/ETH)
    offchain_yields = [
        {"chain": "Base", "protocol": "Aave V3", "apy": 8.2, "asset": "USDC",
         "chain_id": BASE_CHAIN_ID, "token": USDC_BASE},
        {"chain": "Ethereum", "protocol": "Morpho", "apy": 9.1, "asset": "USDC",
         "chain_id": ETH_CHAIN_ID, "token": USDC_ETH},
    ]
    best_offchain = max(offchain_yields, key=lambda x: x["apy"])

    if best_offchain["apy"] > solana_apy + 2.0:
        route = get_cross_chain_route(
            SOLANA_CHAIN_ID, best_offchain["chain_id"],
            USDC_SOLANA, best_offchain["token"], 500.0
        )
        return {
            "better_yield_found": True,
            "protocol": best_offchain["protocol"],
            "chain": best_offchain["chain"],
            "apy": best_offchain["apy"],
            "lifi_route": route,
            "message": (
                f"LI.FI found {best_offchain['apy']}% APY on {best_offchain['protocol']} ({best_offchain['chain']}) "
                f"vs {solana_apy}% on Solana. Bridge cost included in route."
            ),
        }
    return {"better_yield_found": False, "solana_apy": solana_apy}


def _format_route(data: dict, amount_usd: float) -> dict:
    action = data.get("action", {})
    estimate = data.get("estimate", {})
    return {
        "status": "found",
        "from_chain": action.get("fromChainId"),
        "to_chain": action.get("toChainId"),
        "from_amount_usd": amount_usd,
        "to_amount_usd": float(estimate.get("toAmountUSD", amount_usd)),
        "gas_cost_usd": float(estimate.get("gasCosts", [{}])[0].get("amountUSD", 0)),
        "bridge": data.get("tool", "lifi"),
        "execution_duration_sec": estimate.get("executionDuration", 60),
        "steps": [s.get("type") for s in data.get("includedSteps", [])],
        "lifi_url": "https://li.fi",
    }


def _fallback_route(from_chain: str, to_chain: str, amount_usd: float, error: str) -> dict:
    return {
        "status": "simulated",
        "from_chain": from_chain,
        "to_chain": to_chain,
        "from_amount_usd": amount_usd,
        "to_amount_usd": amount_usd * 0.998,
        "gas_cost_usd": 0.12,
        "bridge": "Stargate via LI.FI",
        "execution_duration_sec": 45,
        "steps": ["swap", "bridge", "swap"],
        "note": error or "LI.FI route simulated for demo",
        "lifi_url": "https://li.fi",
    }
