from typing import Dict, Set, Callable, Any
import asyncio
import json
from datetime import datetime


class WebTransportManager:
    """
    WebTransport connection manager for real-time updates
    Modern replacement for WebSockets with HTTP/3
    """

    def __init__(self):
        self.active_sessions: Dict[str, Any] = {}
        self.user_sessions: Dict[int, Set[str]] = {}
        self._callbacks: Dict[str, Set[Callable]] = {}

    async def connect(self, session_id: str, user_id: int, session) -> None:
        """
        Register a new WebTransport session
        """
        self.active_sessions[session_id] = {
            "user_id": user_id,
            "session": session,
            "connected_at": datetime.utcnow(),
        }

        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = set()
        self.user_sessions[user_id].add(session_id)

    async def disconnect(self, session_id: str) -> None:
        """
        Remove a WebTransport session
        """
        if session_id in self.active_sessions:
            user_id = self.active_sessions[session_id]["user_id"]
            del self.active_sessions[session_id]

            if user_id in self.user_sessions:
                self.user_sessions[user_id].discard(session_id)
                if not self.user_sessions[user_id]:
                    del self.user_sessions[user_id]

    async def send_to_user(self, user_id: int, message: Dict[str, Any]) -> None:
        """
        Send message to all sessions of a specific user
        """
        if user_id not in self.user_sessions:
            return

        message_json = json.dumps(message)
        disconnected_sessions = []

        for session_id in self.user_sessions[user_id]:
            if session_id in self.active_sessions:
                try:
                    session = self.active_sessions[session_id]["session"]
                    await session.send(message_json.encode())
                except Exception as e:
                    print(f"Error sending to session {session_id}: {e}")
                    disconnected_sessions.append(session_id)

        for session_id in disconnected_sessions:
            await self.disconnect(session_id)

    async def broadcast(self, message: Dict[str, Any]) -> None:
        """
        Broadcast message to all connected sessions
        """
        message_json = json.dumps(message)
        disconnected_sessions = []

        for session_id, session_data in self.active_sessions.items():
            try:
                session = session_data["session"]
                await session.send(message_json.encode())
            except Exception as e:
                print(f"Error broadcasting to {session_id}: {e}")
                disconnected_sessions.append(session_id)

        for session_id in disconnected_sessions:
            await self.disconnect(session_id)

    async def send_download_update(self, user_id: int, torrent_hash: str, progress: float, speed: int) -> None:
        """
        Send download progress update to user
        """
        await self.send_to_user(user_id, {
            "type": "download_progress",
            "torrent_hash": torrent_hash,
            "progress": progress,
            "download_speed": speed,
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def send_media_added(self, user_id: int, media_type: str, media_id: int, title: str) -> None:
        """
        Notify user that media was added to library
        """
        await self.send_to_user(user_id, {
            "type": "media_added",
            "media_type": media_type,
            "media_id": media_id,
            "title": title,
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def send_search_complete(self, user_id: int, query: str, results_count: int) -> None:
        """
        Notify user that search is complete
        """
        await self.send_to_user(user_id, {
            "type": "search_complete",
            "query": query,
            "results_count": results_count,
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def send_download_complete(self, user_id: int, media_id: int, media_type: str, title: str) -> None:
        """
        Notify user that download completed
        """
        await self.send_to_user(user_id, {
            "type": "download_complete",
            "media_id": media_id,
            "media_type": media_type,
            "title": title,
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def send_rss_update(self, user_id: int, new_releases_count: int) -> None:
        """
        Notify user of new RSS releases
        """
        await self.send_to_user(user_id, {
            "type": "rss_update",
            "new_releases": new_releases_count,
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def send_transcoding_progress(
        self,
        user_id: int,
        job_id: int,
        progress: float,
        fps: float,
        speed: str,
        frame: int,
        bitrate: str,
    ) -> None:
        """
        Send transcoding progress update to user
        """
        await self.send_to_user(user_id, {
            "type": "transcoding_progress",
            "job_id": job_id,
            "progress": progress,
            "fps": fps,
            "speed": speed,
            "frame": frame,
            "bitrate": bitrate,
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def send_transcoding_complete(
        self,
        user_id: int,
        job_id: int,
        media_title: str,
        success: bool,
        error_message: str = None,
    ) -> None:
        """
        Notify user that transcoding completed
        """
        await self.send_to_user(user_id, {
            "type": "transcoding_complete",
            "job_id": job_id,
            "media_title": media_title,
            "success": success,
            "error_message": error_message,
            "timestamp": datetime.utcnow().isoformat(),
        })

    def get_active_users(self) -> Set[int]:
        """
        Get set of currently connected user IDs
        """
        return set(self.user_sessions.keys())

    def get_session_count(self) -> int:
        """
        Get total number of active sessions
        """
        return len(self.active_sessions)

    def get_user_session_count(self, user_id: int) -> int:
        """
        Get number of active sessions for a user
        """
        return len(self.user_sessions.get(user_id, set()))


webtransport_manager = WebTransportManager()
