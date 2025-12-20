import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.agents.graph import graph_app
from app.api.schemas import Perception, WorldObject, GameMode

async def main():
    print(f"🚀 Starting Manual Graph Run...")
    print(f"📡 LangSmith Project: {settings.LANGCHAIN_PROJECT}")
    print(f"🔍 Tracing Enabled: {settings.LANGCHAIN_TRACING_V2}")
    
    mock_perception = Perception(
        time_hour=22,
        day=1,
        mode=GameMode.DREAM,
        location_id="bedroom",
        player_nearby=False,
        recent_events=["quiet_humming", "lights_flickering"],
    )

    try:
        
        pass
    except Exception as e:
        pass

if __name__ == "__main__":
    asyncio.run(main())
