from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional
import uuid

from app.models import Playbook, Session as SessionModel, SessionEvent, SessionEventType, SessionStatus, User, UserRole
from app.schemas import (
    AdminAnalyticsDashboard,
    AdminAnalyticsOverview,
    AdminDeviationBreakdown,
    AdminInterventionRow,
    AdminPlaybookRow,
    AdminTraderRow,
    AdminTrendPoint,
)


SEVERE_LEVELS = {"high", "critical", "HIGH", "CRITICAL"}


@dataclass
class SessionMetrics:
    session_id: uuid.UUID
    user_id: uuid.UUID
    playbook_id: uuid.UUID
    start_time: datetime
    end_time: Optional[datetime]
    status: SessionStatus
    deviation_events: int
    adherence_events: int
    relevant_events: int
    latest_accumulated_deviation: int
    total_deviation_cost: float
    total_unauthorized_gain: float
    severe_events: int
    family_counts: Counter[str]
    type_counts: Counter[str]
    severity_counts: Counter[str]
    rule_counts: Counter[str]
    cost_by_family: Counter[str]
    cost_by_type: Counter[str]

    @property
    def adherence_rate(self) -> float:
        if self.relevant_events > 0:
            return self.adherence_events / self.relevant_events
        if self.latest_accumulated_deviation > 0:
            return max(0.0, 1.0 - min(self.latest_accumulated_deviation / 10.0, 1.0))
        return 1.0


def _safe_datetime(value: Optional[datetime]) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _as_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.replace("$", "").replace(",", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _as_int(value: Any) -> Optional[int]:
    number = _as_float(value)
    if number is None:
        return None
    return int(number)


def _event_labels(event: SessionEvent) -> tuple[str, str, str, str]:
    data = event.event_data or {}
    family = (
        data.get("deviation_family")
        or data.get("family")
        or data.get("rule_category")
        or event.type.value
    )
    deviation_type = (
        data.get("deviation_type")
        or data.get("type")
        or data.get("rule")
        or event.type.value
    )
    severity = data.get("severity") or ("HIGH" if event.type == SessionEventType.DEVIATION else "INFO")
    rule = (
        data.get("rule_name")
        or data.get("rule")
        or data.get("rule_id")
        or deviation_type
    )
    return str(family), str(deviation_type), str(severity), str(rule)


def _extract_cost(event: SessionEvent) -> float:
    data = event.event_data or {}
    for key in (
        "finalized_cost",
        "candidate_cost",
        "total_deviation_cost",
        "deviation_cost",
        "cost",
        "price_delta",
    ):
        value = _as_float(data.get(key))
        if value is not None:
            return max(value, 0.0)
    return 0.0


def _extract_unauthorized_gain(event: SessionEvent) -> float:
    data = event.event_data or {}
    for key in ("unauthorized_gain", "total_unauthorized_gain"):
        value = _as_float(data.get(key))
        if value is not None:
            return max(value, 0.0)
    return 0.0


def _extract_accumulated_deviation(events: Iterable[SessionEvent]) -> int:
    latest = 0
    for event in events:
        data = event.event_data or {}
        candidate = _as_int(data.get("accumulated_deviation"))
        if candidate is not None:
            latest = max(latest, candidate)
    return latest


def _is_deviation_event(event: SessionEvent) -> bool:
    data = event.event_data or {}
    return event.type == SessionEventType.DEVIATION or bool(data.get("deviation"))


def _is_adherence_event(event: SessionEvent) -> bool:
    if event.type == SessionEventType.ADHERENCE:
        data = event.event_data or {}
        return not bool(data.get("deviation"))
    return False


def build_admin_dashboard(
    users: List[User],
    playbooks: List[Playbook],
    sessions: List[SessionModel],
    events: List[SessionEvent],
) -> AdminAnalyticsDashboard:
    users = [user for user in users if user.role == UserRole.TRADER]
    playbooks_by_id = {playbook.id: playbook for playbook in playbooks}
    sessions_by_user: Dict[uuid.UUID, List[SessionModel]] = defaultdict(list)
    events_by_session: Dict[uuid.UUID, List[SessionEvent]] = defaultdict(list)

    for session in sessions:
        sessions_by_user[session.user_id].append(session)
    for event in events:
        events_by_session[event.session_id].append(event)

    session_metrics: Dict[uuid.UUID, SessionMetrics] = {}
    deviation_family_totals: Counter[str] = Counter()
    deviation_type_totals: Counter[str] = Counter()
    deviation_severity_totals: Counter[str] = Counter()
    cost_by_family: Counter[str] = Counter()
    cost_by_type: Counter[str] = Counter()

    for session in sessions:
        session_events = sorted(events_by_session.get(session.id, []), key=lambda item: item.timestamp)
        family_counts: Counter[str] = Counter()
        type_counts: Counter[str] = Counter()
        severity_counts: Counter[str] = Counter()
        rule_counts: Counter[str] = Counter()
        session_cost_by_family: Counter[str] = Counter()
        session_cost_by_type: Counter[str] = Counter()
        deviation_events = 0
        adherence_events = 0
        severe_events = 0
        total_cost = 0.0
        total_unauthorized_gain = 0.0

        for event in session_events:
            family, deviation_type, severity, rule = _event_labels(event)
            cost = _extract_cost(event)
            gain = _extract_unauthorized_gain(event)

            if _is_deviation_event(event):
                deviation_events += 1
                family_counts[family] += 1
                type_counts[deviation_type] += 1
                severity_counts[severity] += 1
                rule_counts[rule] += 1
                session_cost_by_family[family] += cost
                session_cost_by_type[deviation_type] += cost
                total_cost += cost
                total_unauthorized_gain += gain
                if severity in SEVERE_LEVELS:
                    severe_events += 1
            elif _is_adherence_event(event):
                adherence_events += 1

        metrics = SessionMetrics(
            session_id=session.id,
            user_id=session.user_id,
            playbook_id=session.playbook_id,
            start_time=_safe_datetime(session.start_time),
            end_time=session.end_time,
            status=session.status,
            deviation_events=deviation_events,
            adherence_events=adherence_events,
            relevant_events=deviation_events + adherence_events,
            latest_accumulated_deviation=_extract_accumulated_deviation(session_events),
            total_deviation_cost=round(total_cost, 2),
            total_unauthorized_gain=round(total_unauthorized_gain, 2),
            severe_events=severe_events,
            family_counts=family_counts,
            type_counts=type_counts,
            severity_counts=severity_counts,
            rule_counts=rule_counts,
            cost_by_family=session_cost_by_family,
            cost_by_type=session_cost_by_type,
        )
        session_metrics[session.id] = metrics
        deviation_family_totals.update(family_counts)
        deviation_type_totals.update(type_counts)
        deviation_severity_totals.update(severity_counts)
        cost_by_family.update(session_cost_by_family)
        cost_by_type.update(session_cost_by_type)

    trader_rows: List[AdminTraderRow] = []
    intervention_rows: List[AdminInterventionRow] = []
    trend_buckets: Dict[str, Dict[str, float]] = defaultdict(
        lambda: {
            "sessions": 0,
            "adherence_total": 0.0,
            "deviation_cost": 0.0,
            "deviation_events": 0.0,
        }
    )
    playbook_rollups: Dict[uuid.UUID, Dict[str, Any]] = defaultdict(
        lambda: {
            "name": "Unknown Playbook",
            "user_ids": set(),
            "sessions_count": 0,
            "adherence_total": 0.0,
            "deviation_cost": 0.0,
            "deviation_events": 0,
            "rule_counts": Counter(),
        }
    )

    now = datetime.now(timezone.utc)

    for user in users:
        user_sessions = sorted(
            sessions_by_user.get(user.id, []),
            key=lambda item: _safe_datetime(item.start_time),
            reverse=True,
        )
        user_metrics = [session_metrics[session.id] for session in user_sessions if session.id in session_metrics]

        total_sessions = len(user_metrics)
        total_cost = round(sum(metric.total_deviation_cost for metric in user_metrics), 2)
        total_gain = round(sum(metric.total_unauthorized_gain for metric in user_metrics), 2)
        total_deviations = sum(metric.deviation_events for metric in user_metrics)
        severe_events = sum(metric.severe_events for metric in user_metrics)
        adherence_rate = (
            sum(metric.adherence_rate for metric in user_metrics) / total_sessions if total_sessions else 1.0
        )

        family_counts: Counter[str] = Counter()
        type_counts: Counter[str] = Counter()
        rule_counts: Counter[str] = Counter()
        for metric in user_metrics:
            family_counts.update(metric.family_counts)
            type_counts.update(metric.type_counts)
            rule_counts.update(metric.rule_counts)

            bucket = metric.start_time.date().isoformat()
            trend_buckets[bucket]["sessions"] += 1
            trend_buckets[bucket]["adherence_total"] += metric.adherence_rate
            trend_buckets[bucket]["deviation_cost"] += metric.total_deviation_cost
            trend_buckets[bucket]["deviation_events"] += metric.deviation_events

            playbook = playbooks_by_id.get(metric.playbook_id)
            playbook_rollup = playbook_rollups[metric.playbook_id]
            playbook_rollup["name"] = playbook.name if playbook else "Unknown Playbook"
            playbook_rollup["user_ids"].add(user.id)
            playbook_rollup["sessions_count"] += 1
            playbook_rollup["adherence_total"] += metric.adherence_rate
            playbook_rollup["deviation_cost"] += metric.total_deviation_cost
            playbook_rollup["deviation_events"] += metric.deviation_events
            playbook_rollup["rule_counts"].update(metric.rule_counts)

        latest_session = user_sessions[0] if user_sessions else None
        recent_sessions = [
            metric for metric in user_metrics if metric.start_time >= now - timedelta(days=7)
        ]
        prior_sessions = [
            metric
            for metric in user_metrics
            if now - timedelta(days=14) <= metric.start_time < now - timedelta(days=7)
        ]
        recent_avg = (
            sum(metric.adherence_rate for metric in recent_sessions) / len(recent_sessions)
            if recent_sessions
            else adherence_rate
        )
        prior_avg = (
            sum(metric.adherence_rate for metric in prior_sessions) / len(prior_sessions)
            if prior_sessions
            else adherence_rate
        )
        drift_delta = round((recent_avg - prior_avg) * 100, 2)
        recent_velocity = round(sum(metric.deviation_events for metric in recent_sessions) / max(len(recent_sessions), 1), 2)
        risk_score = round(
            total_cost / 25.0
            + severe_events * 8.0
            + total_deviations * 2.0
            + max(0.0, -drift_delta) * 0.75
            + recent_velocity * 4.0,
            2,
        )

        if risk_score >= 40:
            risk_label = "critical"
        elif risk_score >= 22:
            risk_label = "high"
        elif risk_score >= 10:
            risk_label = "medium"
        else:
            risk_label = "low"

        trader_row = AdminTraderRow(
            user_id=user.id,
            email=user.email,
            latest_session_id=latest_session.id if latest_session else None,
            latest_session_status=latest_session.status if latest_session else None,
            sessions_count=total_sessions,
            adherence_rate=round(adherence_rate * 100, 1),
            total_deviation_cost=total_cost,
            total_unauthorized_gain=total_gain,
            total_deviation_events=total_deviations,
            severe_deviation_events=severe_events,
            top_deviation_family=family_counts.most_common(1)[0][0] if family_counts else None,
            top_deviation_type=type_counts.most_common(1)[0][0] if type_counts else None,
            last_active_at=_safe_datetime(latest_session.start_time) if latest_session else None,
            risk_rank_score=risk_score,
            risk_rank_label=risk_label,
            drift_delta_7d=drift_delta,
        )
        trader_rows.append(trader_row)

        drivers: List[str] = []
        if total_cost > 0:
            drivers.append(f"${total_cost:.2f} total deviation cost")
        if recent_velocity >= 2:
            drivers.append(f"{recent_velocity:.1f} deviations per recent session")
        if severe_events > 0:
            drivers.append(f"{severe_events} severe deviations recorded")
        if rule_counts:
            rule_name, count = rule_counts.most_common(1)[0]
            if count > 1:
                drivers.append(f"Repeated rule break: {rule_name} ({count}x)")
        if drift_delta < -5:
            drivers.append(f"Adherence down {abs(drift_delta):.1f} pts over 7d")
        if not drivers:
            drivers.append("Stable behavior, monitor for new drift")

        if risk_score >= 35:
            priority_label = "urgent"
        elif risk_score >= 22:
            priority_label = "restrict"
        elif risk_score >= 10:
            priority_label = "coach"
        else:
            priority_label = "monitor"

        intervention_rows.append(
            AdminInterventionRow(
                user_id=user.id,
                email=user.email,
                latest_session_id=latest_session.id if latest_session else None,
                priority_score=risk_score,
                priority_label=priority_label,
                drivers=drivers[:3],
                total_deviation_cost=total_cost,
                recent_deviation_velocity=recent_velocity,
                repeated_rule_breaks=sum(1 for count in rule_counts.values() if count > 1),
                severe_events=severe_events,
            )
        )

    trader_rows.sort(key=lambda row: (-row.risk_rank_score, row.email))
    intervention_rows.sort(key=lambda row: (-row.priority_score, row.email))

    trends = [
        AdminTrendPoint(
            bucket=bucket,
            sessions=int(values["sessions"]),
            adherence_rate=round((values["adherence_total"] / values["sessions"]) * 100, 1),
            deviation_cost=round(values["deviation_cost"], 2),
            deviation_events=int(values["deviation_events"]),
        )
        for bucket, values in sorted(trend_buckets.items())
        if values["sessions"] > 0
    ]

    playbook_rows = [
        AdminPlaybookRow(
            playbook_id=playbook_id,
            playbook_name=values["name"],
            trader_count=len(values["user_ids"]),
            sessions_count=values["sessions_count"],
            adherence_rate=round((values["adherence_total"] / max(values["sessions_count"], 1)) * 100, 1),
            total_deviation_cost=round(values["deviation_cost"], 2),
            total_deviation_events=values["deviation_events"],
            most_broken_rule=values["rule_counts"].most_common(1)[0][0] if values["rule_counts"] else None,
        )
        for playbook_id, values in playbook_rollups.items()
    ]
    playbook_rows.sort(key=lambda row: (-row.total_deviation_cost, row.playbook_name))

    overview = AdminAnalyticsOverview(
        total_traders=len(users),
        active_sessions=sum(1 for session in sessions if session.status == SessionStatus.STARTED),
        completed_sessions=sum(1 for session in sessions if session.status == SessionStatus.COMPLETED),
        adherence_rate=round(
            (sum(row.adherence_rate for row in trader_rows) / max(len(trader_rows), 1)),
            1,
        ),
        total_deviation_cost=round(sum(row.total_deviation_cost for row in trader_rows), 2),
        total_unauthorized_gain=round(sum(row.total_unauthorized_gain for row in trader_rows), 2),
        total_deviation_events=sum(row.total_deviation_events for row in trader_rows),
        at_risk_traders=sum(1 for row in trader_rows if row.risk_rank_label in {"high", "critical"}),
    )

    deviations = AdminDeviationBreakdown(
        by_family=dict(sorted(deviation_family_totals.items(), key=lambda item: (-item[1], item[0]))),
        by_type=dict(sorted(deviation_type_totals.items(), key=lambda item: (-item[1], item[0]))),
        by_severity=dict(sorted(deviation_severity_totals.items(), key=lambda item: (-item[1], item[0]))),
        cost_by_family={key: round(value, 2) for key, value in cost_by_family.items()},
        cost_by_type={key: round(value, 2) for key, value in cost_by_type.items()},
    )

    return AdminAnalyticsDashboard(
        overview=overview,
        trends=trends,
        traders=trader_rows,
        deviations=deviations,
        playbooks=playbook_rows,
        interventions=intervention_rows,
    )
