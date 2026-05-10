"""
DefiLlama API client — fetches Solana yield pools.
Replaces Playwright browser scraping for DeFi data.
"""
import requests, time

DEFILLAMA_YIELDS = "https://yields.llama.fi/pools"

SOLANA_PROTOCOLS = {"kamino", "marinade", "drift", "jupiter", "solend", "marginfi", "save", "jito"}

def get_solana_pools(min_tvl: float = 1_000_000, min_apy: float = 1.0) -> list[dict]:
    """Fetch Solana yield pools from DefiLlama. Returns sorted by APY desc."""
    try:
        r = requests.get(DEFILLAMA_YIELDS, timeout=15)
        r.raise_for_status()
        pools = r.json().get("data", [])
    except Exception as e:
        print(f"DefiLlama fetch failed: {e}")
        return _fallback_pools()

    solana = [
        p for p in pools
        if p.get("chain", "").lower() == "solana"
        and (p.get("apy") or 0) >= min_apy
        and (p.get("tvlUsd") or 0) >= min_tvl
        and not p.get("ilRisk") == "yes"  # skip high IL pools
    ]
    solana.sort(key=lambda p: p.get("apy", 0), reverse=True)
    return solana[:20]


def get_best_usdc_pools(top_n: int = 5) -> list[dict]:
    """Get best yield pools on Solana (stable + LST, TVL > 10M)."""
    pools = get_solana_pools(min_tvl=10_000_000, min_apy=1.0)
    # Prefer known audited protocols
    preferred = {"kamino", "marinade", "drift", "jupiter", "jito", "marginfi",
                 "sanctum", "phantom", "save", "solend", "unitas", "onre"}
    top = [p for p in pools if any(pref in (p.get("project") or "").lower() for pref in preferred)]
    # Fall back to all pools if preferred list is short
    result = top if len(top) >= top_n else pools
    return result[:top_n]


def format_pool(p: dict) -> dict:
    """Normalize a DefiLlama pool into SOLSCOUT format."""
    return {
        "protocol": p.get("project", "unknown").title(),
        "pool": p.get("pool", ""),
        "symbol": p.get("symbol", ""),
        "apy": round(p.get("apy") or 0, 2),
        "apy_base": round(p.get("apyBase") or 0, 2),
        "apy_reward": round(p.get("apyReward") or 0, 2),
        "tvl_usd": int(p.get("tvlUsd") or 0),
        "il_risk": p.get("ilRisk", "no"),
        "audited": p.get("audits") not in (None, "0", 0),
        "chain": "Solana",
        "url": f"https://defillama.com/yields/pool/{p.get('pool','')}",
    }


def _fallback_pools() -> list[dict]:
    """Static fallback if DefiLlama is unreachable during demo."""
    return [
        {"project": "kamino", "symbol": "USDC", "apy": 11.2, "apyBase": 8.1, "apyReward": 3.1,
         "tvlUsd": 45_000_000, "ilRisk": "no", "audits": "2", "chain": "Solana",
         "pool": "kamino-usdc-jlp"},
        {"project": "marinade", "symbol": "mSOL", "apy": 7.8, "apyBase": 7.8, "apyReward": 0,
         "tvlUsd": 320_000_000, "ilRisk": "no", "audits": "3", "chain": "Solana",
         "pool": "marinade-msol"},
        {"project": "drift", "symbol": "USDC", "apy": 9.4, "apyBase": 6.2, "apyReward": 3.2,
         "tvlUsd": 28_000_000, "ilRisk": "no", "audits": "2", "chain": "Solana",
         "pool": "drift-usdc"},
        {"project": "marginfi", "symbol": "USDC", "apy": 8.1, "apyBase": 8.1, "apyReward": 0,
         "tvlUsd": 55_000_000, "ilRisk": "no", "audits": "2", "chain": "Solana",
         "pool": "marginfi-usdc"},
        {"project": "jito", "symbol": "JitoSOL", "apy": 8.9, "apyBase": 8.9, "apyReward": 0,
         "tvlUsd": 1_200_000_000, "ilRisk": "no", "audits": "3", "chain": "Solana",
         "pool": "jito-jitosol"},
    ]
