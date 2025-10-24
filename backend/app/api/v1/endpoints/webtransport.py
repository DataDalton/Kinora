from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from app.core.webtransport import webtransport_manager
from app.api.v1.endpoints.auth import get_current_user
from app.schemas.user import User

router = APIRouter()


@router.websocket("/stream")
async def webtransport_endpoint(websocket: WebSocket):
    """
    WebTransport endpoint for real-time updates

    Note: This is a WebSocket fallback for development
    In production with HTTP/3, this will be replaced with native WebTransport
    """
    await websocket.accept()

    # Get user from token in query params
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008, reason="Missing authentication token")
        return

    try:
        # Validate token and get user
        from app.core.security import verify_token
        payload = verify_token(token, "access")
        if not payload:
            await websocket.close(code=1008, reason="Invalid token")
            return

        user_id = payload.get("user_id")
        if not user_id:
            await websocket.close(code=1008, reason="Invalid token payload")
            return

        # Generate session ID
        import uuid
        session_id = str(uuid.uuid4())

        # Register session
        await webtransport_manager.connect(session_id, user_id, websocket)

        try:
            # Keep connection alive and listen for messages
            while True:
                data = await websocket.receive_text()
                # Handle incoming messages if needed (ping/pong, etc.)
                if data == "ping":
                    await websocket.send_text("pong")

        except WebSocketDisconnect:
            pass
        finally:
            await webtransport_manager.disconnect(session_id)

    except Exception as e:
        print(f"WebTransport error: {e}")
        await websocket.close(code=1011, reason="Internal server error")
