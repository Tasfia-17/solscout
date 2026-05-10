# SOLSCOUT

Solana Yield Intelligence - AI agents that hunt, audit, and execute yield opportunities on Solana.

## Demo Video

🎥 **[Watch the Demo](https://github.com/Tasfia-17/solscout/blob/main/demo-video.md)**

## What it does

SOLSCOUT is a multi-agent system that scans Solana DeFi protocols, finds the best yield opportunities, audits risk with AI agents, and builds ready-to-execute transactions. Built for the Dev3pack Global Hackathon 2026.

**Core Flow:**
1. **Hunt** - Agents scan 50+ Solana yield pools via DefiLlama API
2. **Audit** - Virtuals Risk Agent evaluates safety, TVL, audit status  
3. **Execute** - Jupiter swap + vault deposit transaction ready to sign

## Features

- **Live Solana Data** - Real yield rates from Kamino, Marinade, Drift, Jupiter, marginfi
- **AI Risk Auditing** - Virtuals GAME Framework agent scores opportunities 0-100
- **Cross-chain Check** - LI.FI integration finds better yields on Base/Ethereum
- **Voice Interface** - ElevenLabs conversational AI for hands-free operation
- **On-chain Identity** - Each agent has Solana PDA with Ed25519 signing
- **Real-time Dashboard** - WebSocket-driven glassmorphism UI

## Sponsor Integrations

| Sponsor | Integration |
|---------|-------------|
| **Solana** | Native Solana transactions, Jupiter Quote API, Solana Agent Kit |
| **ElevenLabs** | TTS + Conversational AI for voice briefings |
| **Virtuals** | Risk Agent deployed on Virtuals GAME Framework |
| **LI.FI** | Cross-chain yield routing (Solana ↔ Base/ETH) |
| **Solana Mobile** | PWA works on Seeker phone |

## Quick Start

```bash
git clone https://github.com/Tasfia-17/solscout
cd solscout
pip install -r requirements.txt
cp .env.example .env
# Add your API keys to .env
uvicorn server:app --host 0.0.0.0 --port 8000
```

Open http://localhost:8000

## Demo Mode

Works without API keys - uses fallback data and simulated agents.

Click **Demo** button or run:
```bash
python solscout_orchestrator.py "Find me the safest 10% yield on Solana"
```

## Architecture

```
Frontend (SPA)          WebSocket           Backend
┌─────────────────┐    ┌─────────────┐    ┌──────────────────┐
│ Glassmorphism   │◄──►│ Real-time   │◄──►│ SOLScout         │
│ Dashboard       │    │ Events      │    │ Orchestrator     │
│ - Hunt          │    │             │    │                  │
│ - Briefing      │    │             │    │ ┌──────────────┐ │
│ - Trust         │    │             │    │ │ DefiLlama    │ │
│ - Network       │    │             │    │ │ Client       │ │
└─────────────────┘    └─────────────┘    │ └──────────────┘ │
                                          │ ┌──────────────┐ │
                                          │ │ Virtuals     │ │
                                          │ │ Risk Agent   │ │
                                          │ └──────────────┘ │
                                          │ ┌──────────────┐ │
                                          │ │ Jupiter TX   │ │
                                          │ │ Builder      │ │
                                          │ └──────────────┘ │
                                          └──────────────────┘
```

## Key Files

- `solscout_orchestrator.py` - Main orchestrator, spawns agents
- `defillama_client.py` - Live Solana yield pool data  
- `solana_tx_builder.py` - Jupiter swap + vault deposit transactions
- `virtuals_agent.py` - Risk auditing via Virtuals GAME Framework
- `elevenlabs_client.py` - Voice interface and TTS
- `solana_identity.py` - Agent PDAs with Ed25519 signing
- `lifi_client.py` - Cross-chain yield comparison
- `static/index.html` - Single-page app (63KB, all CSS/JS inline)

## Environment Variables

```bash
IONROUTER_API_KEY=your_ionrouter_key_here
ELEVENLABS_API_KEY=your_elevenlabs_key_here  
VIRTUALS_API_KEY=your_virtuals_key_here
WALLET_PRIVATE_KEY=your_solana_wallet_private_key_base58
```

## Tracks Entered

- **Solana** (Main) - Native Solana transactions and Jupiter integration
- **ElevenLabs** - Conversational AI voice interface
- **Virtuals** - Risk Agent on GAME Framework  
- **LI.FI** - Cross-chain yield routing
- **Solana Mobile** - PWA mobile experience

## Built With

- **Backend**: FastAPI, WebSockets, asyncio
- **Frontend**: Vanilla JS, glassmorphism CSS, WebSocket real-time
- **Solana**: Jupiter Quote API, Solana Agent Kit, Ed25519 signing
- **AI**: ionrouter LLMs, ElevenLabs TTS, Virtuals agents
- **Data**: DefiLlama API, LI.FI routing

## Team

Built for Dev3pack Global Hackathon 2026 by the SOLSCOUT team.
