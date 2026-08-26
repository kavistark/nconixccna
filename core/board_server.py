import threading
import asyncio
import json
import logging
import websockets

logger = logging.getLogger(__name__)

# Memory cache for current session drawing history
drawing_history = []
# Keep track of active WebSocket connections
connected_clients = set()

async def handler(websocket):
    global drawing_history
    connected_clients.add(websocket)
    # Replay drawing history to the newly connected client
    if drawing_history:
        try:
            await websocket.send(json.dumps({
                "type": "history",
                "history": drawing_history
            }))
        except Exception as e:
            logger.debug(f"Error sending history: {e}")

    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                if data.get("type") == "clear":
                    drawing_history.clear()
                elif data.get("type") == "undo":
                    stroke_id = data.get("strokeId")
                    drawing_history = [item for item in drawing_history if item.get("strokeId") != stroke_id]
                elif data.get("type") == "pointer":
                    pass
                else:
                    drawing_history.append(data)
            except Exception as e:
                logger.error(f"Error parsing drawing packet: {e}")

            # Broadcast drawing packets to all other connected clients
            for client in list(connected_clients):
                if client != websocket:
                    try:
                        await client.send(message)
                    except Exception:
                        connected_clients.discard(client)
    except Exception as e:
        logger.debug(f"Connection error: {e}")
    finally:
        connected_clients.discard(websocket)

async def main():
    # Bind to port 8001
    async with websockets.serve(handler, "0.0.0.0", 8001):
        await asyncio.Future()  # Keep running indefinitely

def start_server():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main())
    except OSError as e:
        if getattr(e, 'winerror', None) == 10048 or getattr(e, 'errno', None) == 10048:
            logger.info("Whiteboard WebSocket server already active on port 8001.")
        else:
            logger.error(f"WebSocket server socket error: {e}")
    except Exception as e:
        logger.error(f"WebSocket server main loop failed: {e}")

def start_server_thread():
    thread = threading.Thread(target=start_server, daemon=True)
    thread.start()

