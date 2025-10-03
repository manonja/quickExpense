"""API endpoints for logging and monitoring visualization."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket
from pydantic import BaseModel

from quickexpense.core.config import Settings, get_settings
from quickexpense.services.conversation_logger import create_conversation_logger
from quickexpense.services.performance_analytics import create_performance_analytics

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/monitoring", tags=["monitoring"])


# Dependency for settings
SettingsDep = Annotated[Settings, Depends(get_settings)]


class PerformanceResponse(BaseModel):
    """Response model for performance metrics."""

    total_sessions: int
    successful_sessions: int
    failed_sessions: int
    success_rate: float
    avg_session_time: float
    avg_confidence_score: float
    total_tokens_used: int
    total_estimated_cost: str
    agent_stats: dict[str, Any]
    hourly_load: dict[str, int]
    category_distribution: dict[str, int]


class ConversationSummary(BaseModel):
    """Summary of a conversation."""

    correlation_id: str
    session_id: str | None
    start_time: datetime
    end_time: datetime | None
    entry_count: int
    avg_confidence: float | None


class AgentPerformanceResponse(BaseModel):
    """Response model for agent performance."""

    agent_name: str
    total_requests: int
    success_rate: float
    avg_processing_time: float
    avg_confidence_score: float
    total_tokens_used: int
    estimated_cost: str


class ErrorAnalysisResponse(BaseModel):
    """Response model for error analysis."""

    error_distribution: dict[str, dict[str, list[dict[str, Any]]]]
    total_errors: int
    error_rate: float


@router.get("/performance", response_model=PerformanceResponse)
async def get_system_performance(
    settings: SettingsDep,
    hours: Annotated[int, Query(description="Number of hours to analyze")] = 24,
) -> PerformanceResponse:
    """Get overall system performance metrics."""
    if not settings.enable_performance_monitoring:
        raise HTTPException(
            status_code=503,
            detail="Performance monitoring is disabled",
        )

    try:
        analytics = create_performance_analytics()

        # Calculate time range
        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(hours=hours)

        # Get system performance
        stats = analytics.get_system_performance(start_date, end_date)

        return PerformanceResponse(
            total_sessions=stats.total_sessions,
            successful_sessions=stats.successful_sessions,
            failed_sessions=stats.failed_sessions,
            success_rate=(
                stats.successful_sessions / stats.total_sessions
                if stats.total_sessions > 0
                else 0
            ),
            avg_session_time=stats.avg_session_time,
            avg_confidence_score=stats.avg_confidence_score,
            total_tokens_used=stats.total_tokens_used,
            total_estimated_cost=f"${stats.total_estimated_cost:.2f}",
            agent_stats={
                name: {
                    "total_requests": agent.total_requests,
                    "success_rate": agent.success_rate,
                    "avg_processing_time": agent.avg_processing_time,
                    "avg_confidence": agent.avg_confidence_score,
                }
                for name, agent in stats.agent_stats.items()
            },
            hourly_load=stats.hourly_load,
            category_distribution=stats.category_distribution,
        )

    except Exception as e:
        logger.error("Error getting system performance: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving performance data: {e!s}",
        ) from e


@router.get("/agents/{agent_name}/performance", response_model=AgentPerformanceResponse)
async def get_agent_performance(
    agent_name: str,
    settings: SettingsDep,
    hours: int = Query(default=24, description="Number of hours to analyze"),
) -> AgentPerformanceResponse:
    """Get performance metrics for a specific agent."""
    if not settings.enable_performance_monitoring:
        raise HTTPException(
            status_code=503,
            detail="Performance monitoring is disabled",
        )

    try:
        analytics = create_performance_analytics()

        # Calculate time range
        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(hours=hours)

        # Get agent performance
        stats = analytics.get_agent_performance(agent_name, start_date, end_date)

        if agent_name not in stats:
            raise HTTPException(
                status_code=404,
                detail=f"No performance data found for agent: {agent_name}",
            )

        agent_stats = stats[agent_name]

        return AgentPerformanceResponse(
            agent_name=agent_name,
            total_requests=agent_stats.total_requests,
            success_rate=agent_stats.success_rate,
            avg_processing_time=agent_stats.avg_processing_time,
            avg_confidence_score=agent_stats.avg_confidence_score,
            total_tokens_used=agent_stats.total_tokens_used,
            estimated_cost=f"${agent_stats.estimated_cost:.2f}",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting agent performance: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving agent performance: {e!s}",
        ) from e


@router.get("/conversations", response_model=list[ConversationSummary])
async def get_recent_conversations(
    settings: SettingsDep,
    limit: int = Query(
        default=10, le=100, description="Maximum conversations to return"
    ),
    agent_name: str | None = Query(None, description="Filter by agent name"),
) -> list[ConversationSummary]:
    """Get recent conversations."""
    if not settings.enable_conversation_logging:
        raise HTTPException(
            status_code=503,
            detail="Conversation logging is disabled",
        )

    try:
        conversation_logger = create_conversation_logger()
        conversations = conversation_logger.get_recent_conversations(
            limit=limit,
            agent_name=agent_name,
        )

        return [
            ConversationSummary(
                correlation_id=conv["correlation_id"],
                session_id=conv.get("session_id"),
                start_time=datetime.fromisoformat(conv["start_time"]),
                end_time=(
                    datetime.fromisoformat(conv["end_time"])
                    if conv.get("end_time")
                    else None
                ),
                entry_count=conv["entry_count"],
                avg_confidence=conv.get("avg_confidence"),
            )
            for conv in conversations
        ]

    except Exception as e:
        logger.error("Error getting conversations: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving conversations: {e!s}",
        ) from e


@router.get("/conversations/{correlation_id}")
async def get_conversation_detail(
    correlation_id: str,
    settings: SettingsDep,
) -> dict[str, Any]:
    """Get detailed conversation history."""
    if not settings.enable_conversation_logging:
        raise HTTPException(
            status_code=503,
            detail="Conversation logging is disabled",
        )

    try:
        conversation_logger = create_conversation_logger()
        conversation = conversation_logger.get_conversation(correlation_id)

        if not conversation:
            raise HTTPException(
                status_code=404,
                detail=f"Conversation not found: {correlation_id}",
            )

        return conversation.model_dump(mode="json")

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting conversation detail: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving conversation: {e!s}",
        ) from e


@router.get("/errors", response_model=ErrorAnalysisResponse)
async def get_error_analysis(
    settings: SettingsDep,
    hours: int = Query(default=24, description="Number of hours to analyze"),
) -> ErrorAnalysisResponse:
    """Get error analysis."""
    if not settings.enable_performance_monitoring:
        raise HTTPException(
            status_code=503,
            detail="Performance monitoring is disabled",
        )

    try:
        analytics = create_performance_analytics()

        # Calculate time range
        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(hours=hours)

        # Get error analysis
        errors = analytics.get_error_analysis(start_date, end_date)

        # Calculate totals
        total_errors = sum(
            sum(err["count"] for err in error_types)
            for agent_errors in errors.values()
            for error_types in agent_errors.values()
        )

        # Get total requests for error rate
        system_stats = analytics.get_system_performance(start_date, end_date)
        total_requests = sum(
            agent.total_requests for agent in system_stats.agent_stats.values()
        )

        return ErrorAnalysisResponse(
            error_distribution=errors,
            total_errors=total_errors,
            error_rate=total_errors / total_requests if total_requests > 0 else 0,
        )

    except Exception as e:
        logger.error("Error getting error analysis: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving error analysis: {e!s}",
        ) from e


@router.get("/token-usage")
async def get_token_usage(
    settings: SettingsDep,
    hours: int = Query(default=24, description="Number of hours to analyze"),
    group_by: str = Query(
        default="model", description="Group by: model, agent, or day"
    ),
) -> dict[str, Any]:
    """Get token usage report."""
    if not settings.enable_performance_monitoring or not settings.log_token_usage:
        raise HTTPException(
            status_code=503,
            detail="Token usage tracking is disabled",
        )

    try:
        analytics = create_performance_analytics()

        # Calculate time range
        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(hours=hours)

        # Get token usage
        usage_df = analytics.get_token_usage_report(
            start_date=start_date,
            end_date=end_date,
            group_by=group_by,
        )

        if usage_df.empty:
            return {"message": "No token usage data available"}

        # Convert to dict for JSON response
        usage_dict = usage_df.to_dict(orient="index")

        # Format costs
        for data in usage_dict.values():
            if "estimated_cost" in data:
                data["estimated_cost"] = f"${data['estimated_cost']:.4f}"

        return {
            "group_by": group_by,
            "time_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "usage": usage_dict,
        }

    except Exception as e:
        logger.error("Error getting token usage: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving token usage: {e!s}",
        ) from e


@router.get("/confidence-trends")
async def get_confidence_trends(
    settings: SettingsDep,
    agent_name: str | None = Query(None, description="Filter by agent name"),
    hours: int = Query(default=24, description="Number of hours to analyze"),
) -> dict[str, Any]:
    """Get confidence score trends."""
    if not settings.enable_performance_monitoring:
        raise HTTPException(
            status_code=503,
            detail="Performance monitoring is disabled",
        )

    try:
        analytics = create_performance_analytics()

        # Get confidence trends
        trends_df = analytics.get_confidence_trends(
            agent_name=agent_name,
            window_hours=hours,
        )

        if trends_df.empty:
            return {"message": "No confidence trend data available"}

        # Convert to list of records for JSON response
        trends = trends_df.to_dict(orient="records")

        # Format timestamps
        for trend in trends:
            if "hour" in trend:
                trend["hour"] = trend["hour"].isoformat()

        return {
            "agent_name": agent_name or "all",
            "window_hours": hours,
            "trends": trends,
        }

    except Exception as e:
        logger.error("Error getting confidence trends: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving confidence trends: {e!s}",
        ) from e


@router.websocket("/live")
async def websocket_monitoring(
    websocket: WebSocket,
    settings: SettingsDep,
) -> None:
    """WebSocket endpoint for live monitoring."""
    if not settings.enable_performance_monitoring:
        await websocket.close(code=1008, reason="Performance monitoring is disabled")
        return

    await websocket.accept()

    try:
        analytics = create_performance_analytics()

        while True:
            # Get latest performance data
            stats = analytics.get_system_performance()

            # Send update to client
            await websocket.send_json(
                {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "total_sessions": stats.total_sessions,
                    "success_rate": (
                        stats.successful_sessions / stats.total_sessions
                        if stats.total_sessions > 0
                        else 0
                    ),
                    "active_agents": len(stats.agent_stats),
                    "total_tokens_used": stats.total_tokens_used,
                }
            )

            # Wait 5 seconds before next update
            await asyncio.sleep(5)

    except Exception as e:  # noqa: BLE001
        logger.error("WebSocket error: %s", e)
        await websocket.close(code=1011, reason=str(e))
