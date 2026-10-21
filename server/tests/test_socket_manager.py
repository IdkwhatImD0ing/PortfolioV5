"""
Tests for socket_manager.py ConnectionManager.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from socket_manager import ConnectionManager


class TestConnectionManager:
    """Tests for ConnectionManager class."""

    @pytest.fixture
    def manager(self):
        """Create a fresh ConnectionManager for each test."""
        return ConnectionManager()

    @pytest.fixture
    def mock_websocket(self):
        """Create a mock WebSocket."""
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()
        return ws

    async def test_init(self, manager):
        """Test that ConnectionManager initializes with empty connections."""
        assert manager.active_connections == {}

    async def test_connect_adds_client(self, manager, mock_websocket):
        """Test that connect() adds a client to active connections."""
        await manager.connect(mock_websocket, "client_1")
        
        assert "client_1" in manager.active_connections
        assert manager.active_connections["client_1"] == mock_websocket
        mock_websocket.accept.assert_called_once()

    async def test_connect_multiple_clients(self, manager):
        """Test connecting multiple clients."""
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        
        await manager.connect(ws1, "client_1")
        await manager.connect(ws2, "client_2")
        
        assert len(manager.active_connections) == 2
        assert "client_1" in manager.active_connections
        assert "client_2" in manager.active_connections

    async def test_disconnect_removes_client(self, manager, mock_websocket):
        """Test that disconnect() removes a client."""
        await manager.connect(mock_websocket, "client_1")
        await manager.disconnect("client_1")
        
        assert "client_1" not in manager.active_connections

    async def test_disconnect_nonexistent_client_no_error(self, manager):
        """Test that disconnecting a nonexistent client doesn't raise error."""
        # Should not raise KeyError
        await manager.disconnect("nonexistent_client")

    async def test_send_personal_message(self, manager, mock_websocket):
        """Test sending a message to a specific websocket."""
        data = {"message": "Hello"}
        await manager.send_personal_message(data, mock_websocket)
        
        mock_websocket.send_json.assert_called_once_with(data)

    async def test_broadcast_to_all_clients(self, manager):
        """Test broadcasting message to all connected clients."""
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        ws3 = AsyncMock()
        
        await manager.connect(ws1, "client_1")
        await manager.connect(ws2, "client_2")
        await manager.connect(ws3, "client_3")
        
        data = {"type": "notification", "content": "Hello everyone"}
        await manager.broadcast(data)
        
        ws1.send_json.assert_called_with(data)
        ws2.send_json.assert_called_with(data)
        ws3.send_json.assert_called_with(data)

    async def test_broadcast_empty_connections(self, manager):
        """Test broadcasting with no active connections doesn't error."""
        data = {"message": "Hello"}
        # Should not raise any exception
        await manager.broadcast(data)

    async def test_connection_replacement(self, manager):
        """Test that connecting with same client_id replaces the connection."""
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        
        await manager.connect(ws1, "client_1")
        await manager.connect(ws2, "client_1")
        
        assert len(manager.active_connections) == 1
        assert manager.active_connections["client_1"] == ws2
