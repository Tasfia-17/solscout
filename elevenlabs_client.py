"""
ElevenLabs client — TTS + Conversational AI.
Replaces orpheus-3b TTS in llm_client.py / video_briefing.py
"""
import os, requests

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
BASE_URL = "https://api.elevenlabs.io/v1"
HEADERS = {"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"}

# Good default voice — "Rachel" (calm, professional)
DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"


def tts(text: str, voice_id: str = DEFAULT_VOICE_ID) -> bytes:
    """Generate speech with ElevenLabs. Returns MP3 bytes."""
    if not ELEVENLABS_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY not set")
    r = requests.post(
        f"{BASE_URL}/text-to-speech/{voice_id}",
        headers=HEADERS,
        json={
            "text": text,
            "model_id": "eleven_turbo_v2_5",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.content


def get_voices() -> list[dict]:
    """List available voices."""
    r = requests.get(f"{BASE_URL}/voices", headers=HEADERS, timeout=10)
    r.raise_for_status()
    return r.json().get("voices", [])


def create_conversational_agent(name: str, system_prompt: str) -> str:
    """Create an ElevenLabs Conversational AI agent. Returns agent_id."""
    r = requests.post(
        f"{BASE_URL}/convai/agents/create",
        headers=HEADERS,
        json={
            "name": name,
            "conversation_config": {
                "agent": {
                    "prompt": {"prompt": system_prompt},
                    "first_message": "I'm analyzing Solana yield opportunities for you. What's your target APY?",
                    "language": "en",
                },
                "tts": {"voice_id": DEFAULT_VOICE_ID},
            },
        },
        timeout=15,
    )
    r.raise_for_status()
    return r.json().get("agent_id", "")


def get_signed_url(agent_id: str) -> str:
    """Get a signed WebSocket URL for a private conversational agent."""
    r = requests.get(
        f"{BASE_URL}/convai/conversation/get_signed_url",
        headers=HEADERS,
        params={"agent_id": agent_id},
        timeout=10,
    )
    r.raise_for_status()
    return r.json().get("signed_url", "")
