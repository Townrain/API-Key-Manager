"""Statistics routes."""

from fastapi import APIRouter

# Import _app module for patchable names (tests patch key_manager.web._app.*)
import key_manager.web._app as _app_mod
from key_manager.api_models import (
    StatsChartProviderEntry,
    StatsChartResponse,
    StatsChartStatuses,
    StatsProviderEntry,
    StatsResponse,
)
from key_manager.providers import get_display_name

router = APIRouter(tags=["Stats"])


@router.get("/api/stats", response_model=StatsResponse)
async def api_stats():
    """Get key statistics broken down by provider."""
    data = _app_mod._load_keys_data()
    keys_dict = data.get("keys", {})

    stats: dict[str, StatsProviderEntry] = {}
    total = 0

    for _key, info in keys_dict.items():
        total += 1
        provider = info.get("provider", "unknown")
        status = info.get("status", "unknown")

        if provider not in stats:
            stats[provider] = StatsProviderEntry(
                total=0, valid=0, invalid=0, error=0,
                display_name=get_display_name(provider),
            )

        stats[provider].total += 1
        if status == "valid":
            stats[provider].valid += 1
        elif status == "invalid":
            stats[provider].invalid += 1
        else:
            stats[provider].error += 1

    return StatsResponse(
        providers=stats,
        total=total,
    )


@router.get("/api/stats/chart", response_model=StatsChartResponse)
async def api_stats_chart():
    """Get chart data for key status distribution."""
    data = _app_mod._load_keys_data()
    keys_dict = data.get("keys", {})

    providers: dict[str, StatsChartProviderEntry] = {}
    global_statuses = StatsChartStatuses()

    for _key, info in keys_dict.items():
        provider = info.get("provider", "unknown")
        status = info.get("status", "unknown")

        if provider not in providers:
            providers[provider] = StatsChartProviderEntry(
                provider=provider,
                display_name=get_display_name(provider),
                statuses=StatsChartStatuses(),
            )

        if status == "valid":
            providers[provider].statuses.valid += 1
            providers[provider].valid += 1
            global_statuses.valid += 1
        elif status == "invalid":
            providers[provider].statuses.invalid += 1
            providers[provider].invalid += 1
            global_statuses.invalid += 1
        else:
            providers[provider].statuses.error += 1
            providers[provider].error += 1
            global_statuses.error += 1

        providers[provider].total += 1

    return StatsChartResponse(
        providers=list(providers.values()),
        statuses=global_statuses,
    )
