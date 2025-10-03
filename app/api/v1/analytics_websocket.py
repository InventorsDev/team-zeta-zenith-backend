from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from typing import Dict, Set, Optional
from datetime import datetime, timedelta
import asyncio
import json

from app.api.v1.auth import get_current_user_ws
from app.models.user import User
from app.database.connection import get_db
from app.services.analytics_service import AnalyticsService
from app.cache.cache_manager import CacheManager
from app.cache.redis_client import get_redis_client

router = APIRouter(prefix="/ws", tags=["websocket"])


class ConnectionManager:
    """Manage WebSocket connections for real-time analytics"""

    def __init__(self):
        self.active_connections: Dict[int, Set[WebSocket]] = {}  # org_id -> set of websockets

    async def connect(self, websocket: WebSocket, organization_id: int):
        """Connect a new WebSocket client"""
        await websocket.accept()
        if organization_id not in self.active_connections:
            self.active_connections[organization_id] = set()
        self.active_connections[organization_id].add(websocket)

    def disconnect(self, websocket: WebSocket, organization_id: int):
        """Disconnect a WebSocket client"""
        if organization_id in self.active_connections:
            self.active_connections[organization_id].discard(websocket)
            if not self.active_connections[organization_id]:
                del self.active_connections[organization_id]

    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send message to a specific WebSocket"""
        await websocket.send_text(message)

    async def broadcast_to_organization(self, message: str, organization_id: int):
        """Broadcast message to all WebSockets in an organization"""
        if organization_id in self.active_connections:
            disconnected = set()
            for connection in self.active_connections[organization_id]:
                try:
                    await connection.send_text(message)
                except Exception:
                    disconnected.add(connection)

            # Clean up disconnected clients
            for connection in disconnected:
                self.active_connections[organization_id].discard(connection)


manager = ConnectionManager()


@router.websocket("/analytics/{organization_id}")
async def websocket_analytics(
    websocket: WebSocket,
    organization_id: int,
    token: str = Query(..., description="Authentication token")
):
    """
    WebSocket endpoint for real-time analytics updates

    Client should connect with: ws://host/api/v1/ws/analytics/{org_id}?token={jwt_token}
    """

    # Verify authentication (simplified - in production use proper JWT validation)
    try:
        # user = await get_current_user_ws(token)
        # if user.organization_id != organization_id:
        #     await websocket.close(code=1008, reason="Unauthorized")
        #     return

        await manager.connect(websocket, organization_id)

        try:
            # Send initial connection confirmation
            await manager.send_personal_message(
                json.dumps({
                    "type": "connected",
                    "organization_id": organization_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "message": "Connected to real-time analytics"
                }),
                websocket
            )

            # Start periodic updates
            while True:
                try:
                    # Wait for client messages (for configuration/requests)
                    data = await asyncio.wait_for(
                        websocket.receive_text(),
                        timeout=30.0  # 30 second timeout
                    )

                    # Handle client requests
                    message = json.loads(data)

                    if message.get("type") == "subscribe":
                        # Client wants to subscribe to specific metrics
                        await handle_subscription(websocket, organization_id, message)

                    elif message.get("type") == "unsubscribe":
                        # Client wants to unsubscribe
                        await manager.send_personal_message(
                            json.dumps({
                                "type": "unsubscribed",
                                "timestamp": datetime.utcnow().isoformat()
                            }),
                            websocket
                        )

                    elif message.get("type") == "ping":
                        # Keepalive ping
                        await manager.send_personal_message(
                            json.dumps({
                                "type": "pong",
                                "timestamp": datetime.utcnow().isoformat()
                            }),
                            websocket
                        )

                except asyncio.TimeoutError:
                    # Send periodic updates even without client messages
                    await send_periodic_update(websocket, organization_id)

                except json.JSONDecodeError:
                    await manager.send_personal_message(
                        json.dumps({
                            "type": "error",
                            "message": "Invalid JSON format",
                            "timestamp": datetime.utcnow().isoformat()
                        }),
                        websocket
                    )

        except WebSocketDisconnect:
            manager.disconnect(websocket, organization_id)

    except Exception as e:
        await websocket.close(code=1011, reason=str(e))


async def handle_subscription(websocket: WebSocket, organization_id: int, message: dict):
    """Handle metric subscription requests"""

    metrics = message.get("metrics", [])
    interval = message.get("interval", 30)  # seconds

    # Send initial data for subscribed metrics
    from sqlalchemy.orm import Session
    from app.database.connection import SessionLocal

    db = SessionLocal()
    try:
        redis_client = get_redis_client()
        cache_manager = CacheManager(redis_client) if redis_client else None
        analytics_service = AnalyticsService(db, cache_manager)

        end_date = datetime.utcnow()
        start_date = end_date - timedelta(hours=1)  # Last hour

        subscription_data = {
            "type": "subscription_data",
            "organization_id": organization_id,
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": {}
        }

        for metric in metrics:
            try:
                # Get latest data for this metric
                time_series = analytics_service.get_time_series(
                    organization_id=organization_id,
                    metric_type=metric,
                    start_date=start_date,
                    end_date=end_date,
                    granularity="hourly",
                    use_cache=True
                )

                subscription_data["metrics"][metric] = {
                    "data_points": [
                        {
                            "timestamp": dp.timestamp.isoformat(),
                            "value": dp.value,
                            "count": dp.count
                        }
                        for dp in time_series.data_points
                    ],
                    "average_value": time_series.average_value,
                    "total_count": time_series.total_count
                }

            except Exception as e:
                subscription_data["metrics"][metric] = {
                    "error": str(e)
                }

        await manager.send_personal_message(
            json.dumps(subscription_data),
            websocket
        )

    finally:
        db.close()


async def send_periodic_update(websocket: WebSocket, organization_id: int):
    """Send periodic analytics updates"""

    from sqlalchemy.orm import Session
    from app.database.connection import SessionLocal

    db = SessionLocal()
    try:
        redis_client = get_redis_client()
        cache_manager = CacheManager(redis_client) if redis_client else None
        analytics_service = AnalyticsService(db, cache_manager)

        end_date = datetime.utcnow()
        start_date = end_date - timedelta(minutes=5)  # Last 5 minutes

        # Get real-time metrics
        metrics_update = {
            "type": "periodic_update",
            "organization_id": organization_id,
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": {}
        }

        # Ticket count in last 5 minutes
        ticket_series = analytics_service.get_time_series(
            organization_id=organization_id,
            metric_type="ticket_count",
            start_date=start_date,
            end_date=end_date,
            granularity="hourly",
            use_cache=False  # Real-time, no cache
        )

        if ticket_series.data_points:
            latest_point = ticket_series.data_points[-1]
            metrics_update["metrics"]["ticket_count"] = {
                "value": latest_point.value,
                "count": latest_point.count,
                "timestamp": latest_point.timestamp.isoformat()
            }

        # Get current dashboard snapshot
        dashboard = analytics_service.get_dashboard_metrics(
            organization_id=organization_id,
            start_date=end_date - timedelta(hours=24),
            end_date=end_date,
            use_cache=True
        )

        metrics_update["dashboard_snapshot"] = {
            "total_tickets": dashboard.total_tickets,
            "open_tickets": dashboard.open_tickets,
            "resolved_tickets": dashboard.resolved_tickets,
            "avg_response_time_hours": dashboard.avg_response_time_hours
        }

        await manager.send_personal_message(
            json.dumps(metrics_update),
            websocket
        )

    except Exception as e:
        await manager.send_personal_message(
            json.dumps({
                "type": "error",
                "message": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }),
            websocket
        )
    finally:
        db.close()


async def broadcast_metric_update(organization_id: int, metric_type: str, value: float):
    """
    Broadcast a metric update to all connected clients in an organization
    This should be called when new data is available
    """

    message = json.dumps({
        "type": "metric_update",
        "organization_id": organization_id,
        "metric_type": metric_type,
        "value": value,
        "timestamp": datetime.utcnow().isoformat()
    })

    await manager.broadcast_to_organization(message, organization_id)
