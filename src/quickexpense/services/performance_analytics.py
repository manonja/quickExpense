"""Performance analytics module for multi-agent system monitoring."""

from __future__ import annotations

import logging
import sqlite3
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AgentPerformanceStats(BaseModel):
    """Performance statistics for an individual agent."""

    agent_name: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    timeout_count: int = 0
    success_rate: float = 0.0
    avg_processing_time: float = 0.0
    min_processing_time: float = 0.0
    max_processing_time: float = 0.0
    avg_confidence_score: float = 0.0
    total_tokens_used: int = 0
    estimated_cost: Decimal = Decimal("0.00")


class SystemPerformanceStats(BaseModel):
    """Overall system performance statistics."""

    total_sessions: int = 0
    successful_sessions: int = 0
    failed_sessions: int = 0
    avg_session_time: float = 0.0
    avg_confidence_score: float = 0.0
    total_tokens_used: int = 0
    total_estimated_cost: Decimal = Decimal("0.00")
    agent_stats: dict[str, AgentPerformanceStats] = Field(default_factory=dict)
    hourly_load: dict[str, int] = Field(default_factory=dict)
    category_distribution: dict[str, int] = Field(default_factory=dict)
    error_distribution: dict[str, int] = Field(default_factory=dict)


class TokenUsageStats(BaseModel):
    """Token usage statistics by model and agent."""

    model: str
    agent_name: str
    total_requests: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: Decimal = Decimal("0.00")


class PerformanceAnalytics:
    """Analytics engine for multi-agent system performance."""

    # Model pricing (per 1K tokens) - Update as needed
    MODEL_PRICING = {
        "gemini-2.0-flash-exp": {"input": 0.0001, "output": 0.0004},
        "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo": {
            "input": 0.0018,
            "output": 0.0018,
        },
        "microsoft/phi-2": {"input": 0.0001, "output": 0.0001},
        "meta-llama/Llama-3.3-70B-Instruct-Turbo": {"input": 0.0018, "output": 0.0018},
        "Qwen/Qwen2-72B-Instruct": {"input": 0.0018, "output": 0.0018},
    }

    def __init__(
        self,
        conversation_db_path: Path | None = None,
        ag2_runtime_db_path: Path | None = None,
    ):
        """Initialize analytics engine."""
        self.conversation_db_path = conversation_db_path or Path(
            "data/conversation_history.db"
        )
        self.ag2_runtime_db_path = ag2_runtime_db_path or Path("data/agent_logs.db")

    def get_agent_performance(
        self,
        agent_name: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, AgentPerformanceStats]:
        """Get performance statistics for agents."""
        stats: dict[str, AgentPerformanceStats] = {}

        with sqlite3.connect(self.conversation_db_path) as conn:
            # Base query
            query = """
                SELECT
                    agent_name,
                    COUNT(*) as total_requests,
                    SUM(CASE WHEN metadata LIKE '%"success": true%' THEN 1 ELSE 0 END) as successful,
                    SUM(CASE WHEN metadata LIKE '%"error_type": "timeout"%' THEN 1 ELSE 0 END) as timeouts,
                    AVG(processing_time) as avg_time,
                    MIN(processing_time) as min_time,
                    MAX(processing_time) as max_time,
                    AVG(confidence_score) as avg_confidence
                FROM conversation_entries
                WHERE role = 'assistant'
            """

            params = []
            conditions = []

            if agent_name:
                conditions.append("agent_name = ?")
                params.append(agent_name)

            if start_date:
                conditions.append("timestamp >= ?")
                params.append(start_date.isoformat())

            if end_date:
                conditions.append("timestamp <= ?")
                params.append(end_date.isoformat())

            if conditions:
                query += " AND " + " AND ".join(conditions)

            query += " GROUP BY agent_name"

            cursor = conn.execute(query, params)

            for row in cursor:
                agent = row[0]
                total = row[1]
                successful = row[2]
                timeouts = row[3]

                stats[agent] = AgentPerformanceStats(
                    agent_name=agent,
                    total_requests=total,
                    successful_requests=successful,
                    failed_requests=total - successful,
                    timeout_count=timeouts,
                    success_rate=successful / total if total > 0 else 0,
                    avg_processing_time=row[4] or 0,
                    min_processing_time=row[5] or 0,
                    max_processing_time=row[6] or 0,
                    avg_confidence_score=row[7] or 0,
                )

        # Add token usage and cost data
        token_stats = self._get_token_usage_by_agent(start_date, end_date)
        for agent_name, agent_stats in stats.items():
            if agent_name in token_stats:
                agent_stats.total_tokens_used = token_stats[agent_name]["total_tokens"]
                agent_stats.estimated_cost = token_stats[agent_name]["estimated_cost"]

        return stats

    def get_system_performance(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> SystemPerformanceStats:
        """Get overall system performance statistics."""
        stats = SystemPerformanceStats()

        with sqlite3.connect(self.conversation_db_path) as conn:
            # Get session statistics
            query = """
                SELECT
                    COUNT(*) as total_sessions,
                    SUM(CASE WHEN final_result IS NOT NULL
                        AND json_extract(final_result, '$.success') = 1
                        THEN 1 ELSE 0 END) as successful_sessions,
                    AVG(JULIANDAY(end_time) - JULIANDAY(start_time)) * 86400 as avg_duration,
                    AVG(CASE WHEN final_result IS NOT NULL
                        THEN json_extract(final_result, '$.overall_confidence')
                        ELSE NULL END) as avg_confidence
                FROM conversations
                WHERE 1=1
            """

            params = []
            if start_date:
                query += " AND start_time >= ?"
                params.append(start_date.isoformat())

            if end_date:
                query += " AND end_time <= ?"
                params.append(end_date.isoformat())

            cursor = conn.execute(query, params)
            row = cursor.fetchone()

            if row:
                stats.total_sessions = row[0]
                stats.successful_sessions = row[1] or 0
                stats.failed_sessions = stats.total_sessions - stats.successful_sessions
                stats.avg_session_time = row[2] or 0
                stats.avg_confidence_score = row[3] or 0

        # Get agent statistics
        stats.agent_stats = self.get_agent_performance(start_date, end_date)

        # Get hourly load distribution
        stats.hourly_load = self._get_hourly_load_distribution(start_date, end_date)

        # Get category distribution
        stats.category_distribution = self._get_category_distribution(
            start_date, end_date
        )

        # Get error distribution
        stats.error_distribution = self._get_error_distribution(start_date, end_date)

        # Calculate totals
        stats.total_tokens_used = sum(
            agent.total_tokens_used for agent in stats.agent_stats.values()
        )
        stats.total_estimated_cost = sum(
            agent.estimated_cost for agent in stats.agent_stats.values()
        )

        return stats

    def get_token_usage_report(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        group_by: str = "model",  # Options: model, agent, day
    ) -> pd.DataFrame:
        """Get detailed token usage report."""
        if not self.ag2_runtime_db_path.exists():
            return pd.DataFrame()

        with sqlite3.connect(self.ag2_runtime_db_path) as conn:
            query = """
                SELECT
                    timestamp,
                    json_extract(request, '$.model') as model,
                    json_extract(request, '$.messages[0].name') as agent_name,
                    json_extract(response, '$.usage.prompt_tokens') as prompt_tokens,
                    json_extract(response, '$.usage.completion_tokens') as completion_tokens,
                    json_extract(response, '$.usage.total_tokens') as total_tokens
                FROM chat_completions
                WHERE total_tokens IS NOT NULL
            """

            params = []
            if start_date:
                query += " AND timestamp >= ?"
                params.append(start_date.isoformat())

            if end_date:
                query += " AND timestamp <= ?"
                params.append(end_date.isoformat())

            df = pd.read_sql_query(query, conn, params=params)

            if df.empty:
                return df

            # Parse timestamp
            df["timestamp"] = pd.to_datetime(df["timestamp"])

            # Calculate costs
            df["estimated_cost"] = df.apply(self._calculate_token_cost, axis=1)

            # Group by requested dimension
            if group_by == "model":
                grouped = (
                    df.groupby("model")
                    .agg(
                        {
                            "prompt_tokens": "sum",
                            "completion_tokens": "sum",
                            "total_tokens": "sum",
                            "estimated_cost": "sum",
                            "timestamp": "count",
                        }
                    )
                    .rename(columns={"timestamp": "request_count"})
                )

            elif group_by == "agent":
                grouped = (
                    df.groupby("agent_name")
                    .agg(
                        {
                            "prompt_tokens": "sum",
                            "completion_tokens": "sum",
                            "total_tokens": "sum",
                            "estimated_cost": "sum",
                            "timestamp": "count",
                        }
                    )
                    .rename(columns={"timestamp": "request_count"})
                )

            elif group_by == "day":
                df["date"] = df["timestamp"].dt.date
                grouped = (
                    df.groupby("date")
                    .agg(
                        {
                            "prompt_tokens": "sum",
                            "completion_tokens": "sum",
                            "total_tokens": "sum",
                            "estimated_cost": "sum",
                            "timestamp": "count",
                        }
                    )
                    .rename(columns={"timestamp": "request_count"})
                )

            else:
                grouped = df

            return grouped

    def get_confidence_trends(
        self,
        agent_name: str | None = None,
        window_hours: int = 24,
    ) -> pd.DataFrame:
        """Get confidence score trends over time."""
        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(hours=window_hours)

        with sqlite3.connect(self.conversation_db_path) as conn:
            query = """
                SELECT
                    timestamp,
                    agent_name,
                    confidence_score
                FROM conversation_entries
                WHERE role = 'assistant'
                    AND confidence_score IS NOT NULL
                    AND timestamp >= ?
                    AND timestamp <= ?
            """

            params = [start_date.isoformat(), end_date.isoformat()]

            if agent_name:
                query += " AND agent_name = ?"
                params.append(agent_name)

            query += " ORDER BY timestamp"

            df = pd.read_sql_query(query, conn, params=params)

            if not df.empty:
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                df["hour"] = df["timestamp"].dt.floor("H")

                # Calculate hourly averages
                trends = (
                    df.groupby(["hour", "agent_name"])["confidence_score"]
                    .agg(["mean", "std", "count"])
                    .reset_index()
                )

                return trends

            return df

    def get_error_analysis(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, Any]:
        """Analyze error patterns."""
        with sqlite3.connect(self.conversation_db_path) as conn:
            query = """
                SELECT
                    agent_name,
                    json_extract(metadata, '$.error_type') as error_type,
                    json_extract(metadata, '$.exception_details') as error_details,
                    COUNT(*) as error_count,
                    AVG(processing_time) as avg_time_to_error
                FROM conversation_entries
                WHERE metadata LIKE '%"error"%'
            """

            params = []
            if start_date:
                query += " AND timestamp >= ?"
                params.append(start_date.isoformat())

            if end_date:
                query += " AND timestamp <= ?"
                params.append(end_date.isoformat())

            query += " GROUP BY agent_name, error_type"

            cursor = conn.execute(query, params)

            errors = defaultdict(lambda: defaultdict(list))
            for row in cursor:
                agent = row[0]
                error_type = row[1] or "unknown"
                errors[agent][error_type].append(
                    {
                        "count": row[3],
                        "avg_time": row[4],
                    }
                )

            return dict(errors)

    def _get_token_usage_by_agent(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Get token usage statistics by agent."""
        if not self.ag2_runtime_db_path.exists():
            return {}

        usage = defaultdict(lambda: {"total_tokens": 0, "estimated_cost": Decimal("0")})

        with sqlite3.connect(self.ag2_runtime_db_path) as conn:
            query = """
                SELECT
                    json_extract(request, '$.messages[0].name') as agent_name,
                    json_extract(request, '$.model') as model,
                    SUM(json_extract(response, '$.usage.prompt_tokens')) as prompt_tokens,
                    SUM(json_extract(response, '$.usage.completion_tokens')) as completion_tokens,
                    SUM(json_extract(response, '$.usage.total_tokens')) as total_tokens
                FROM chat_completions
                WHERE total_tokens IS NOT NULL
            """

            params = []
            if start_date:
                query += " AND timestamp >= ?"
                params.append(start_date.isoformat())

            if end_date:
                query += " AND timestamp <= ?"
                params.append(end_date.isoformat())

            query += " GROUP BY agent_name, model"

            cursor = conn.execute(query, params)

            for row in cursor:
                agent = row[0] or "unknown"
                model = row[1]
                prompt_tokens = row[2] or 0
                completion_tokens = row[3] or 0
                total_tokens = row[4] or 0

                usage[agent]["total_tokens"] += total_tokens

                # Calculate cost
                if model in self.MODEL_PRICING:
                    pricing = self.MODEL_PRICING[model]
                    cost = Decimal(prompt_tokens * pricing["input"] / 1000)
                    cost += Decimal(completion_tokens * pricing["output"] / 1000)
                    usage[agent]["estimated_cost"] += cost

        return dict(usage)

    def _get_hourly_load_distribution(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, int]:
        """Get request distribution by hour of day."""
        with sqlite3.connect(self.conversation_db_path) as conn:
            query = """
                SELECT
                    strftime('%H', start_time) as hour,
                    COUNT(*) as count
                FROM conversations
                WHERE 1=1
            """

            params = []
            if start_date:
                query += " AND start_time >= ?"
                params.append(start_date.isoformat())

            if end_date:
                query += " AND start_time <= ?"
                params.append(end_date.isoformat())

            query += " GROUP BY hour ORDER BY hour"

            cursor = conn.execute(query, params)

            distribution = {}
            for row in cursor:
                distribution[f"{row[0]}:00"] = row[1]

            return distribution

    def _get_category_distribution(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, int]:
        """Get expense category distribution."""
        with sqlite3.connect(self.conversation_db_path) as conn:
            query = """
                SELECT
                    json_extract(final_result, '$.final_data.category') as category,
                    COUNT(*) as count
                FROM conversations
                WHERE final_result IS NOT NULL
                    AND json_extract(final_result, '$.success') = 1
            """

            params = []
            if start_date:
                query += " AND start_time >= ?"
                params.append(start_date.isoformat())

            if end_date:
                query += " AND end_time <= ?"
                params.append(end_date.isoformat())

            query += " GROUP BY category"

            cursor = conn.execute(query, params)

            distribution = {}
            for row in cursor:
                category = row[0] or "Unknown"
                distribution[category] = row[1]

            return distribution

    def _get_error_distribution(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, int]:
        """Get error type distribution."""
        with sqlite3.connect(self.conversation_db_path) as conn:
            query = """
                SELECT
                    json_extract(metadata, '$.error_type') as error_type,
                    COUNT(*) as count
                FROM conversation_entries
                WHERE metadata LIKE '%"error_type"%'
            """

            params = []
            if start_date:
                query += " AND timestamp >= ?"
                params.append(start_date.isoformat())

            if end_date:
                query += " AND timestamp <= ?"
                params.append(end_date.isoformat())

            query += " GROUP BY error_type"

            cursor = conn.execute(query, params)

            distribution = {}
            for row in cursor:
                error_type = row[0] or "unknown"
                distribution[error_type] = row[1]

            return distribution

    def _calculate_token_cost(self, row: pd.Series) -> float:
        """Calculate cost for a token usage row."""
        model = row["model"]
        if model not in self.MODEL_PRICING:
            return 0.0

        pricing = self.MODEL_PRICING[model]
        prompt_cost = (row["prompt_tokens"] or 0) * pricing["input"] / 1000
        completion_cost = (row["completion_tokens"] or 0) * pricing["output"] / 1000

        return prompt_cost + completion_cost


# Factory function
def create_performance_analytics(
    conversation_db_path: Path | None = None,
    ag2_runtime_db_path: Path | None = None,
) -> PerformanceAnalytics:
    """Create a performance analytics instance."""
    return PerformanceAnalytics(
        conversation_db_path=conversation_db_path,
        ag2_runtime_db_path=ag2_runtime_db_path,
    )
