from typing import Optional
from datetime import datetime
from app.cache.cache_manager import CacheManager
from app.services.analytics_service import AnalyticsService


class CacheInvalidationHelper:
    """Helper class for cache invalidation on data changes"""

    def __init__(self, cache_manager: CacheManager):
        self.cache_manager = cache_manager

    def invalidate_on_ticket_create(self, organization_id: int):
        """Invalidate caches when a new ticket is created"""
        patterns = [
            f"*org={organization_id}*",
            f"*time_series*ticket_count*{organization_id}*",
            f"*dashboard*{organization_id}*",
            f"*distribution*{organization_id}*"
        ]

        for pattern in patterns:
            self.cache_manager.delete_pattern(pattern)

    def invalidate_on_ticket_update(
        self,
        organization_id: int,
        status_changed: bool = False,
        priority_changed: bool = False,
        assigned: bool = False
    ):
        """Invalidate relevant caches when a ticket is updated"""
        patterns = [
            f"*dashboard*{organization_id}*"
        ]

        if status_changed:
            patterns.extend([
                f"*distribution*status*{organization_id}*",
                f"*time_series*resolution_time*{organization_id}*"
            ])

        if priority_changed:
            patterns.append(f"*distribution*priority*{organization_id}*")

        if assigned:
            patterns.append(f"*distribution*assigned_to*{organization_id}*")

        for pattern in patterns:
            self.cache_manager.delete_pattern(pattern)

    def invalidate_on_response(self, organization_id: int):
        """Invalidate caches when a first response is added"""
        patterns = [
            f"*time_series*response_time*{organization_id}*",
            f"*performance*{organization_id}*",
            f"*dashboard*{organization_id}*"
        ]

        for pattern in patterns:
            self.cache_manager.delete_pattern(pattern)

    def invalidate_on_resolution(self, organization_id: int):
        """Invalidate caches when a ticket is resolved"""
        patterns = [
            f"*time_series*resolution_time*{organization_id}*",
            f"*performance*{organization_id}*",
            f"*dashboard*{organization_id}*",
            f"*distribution*status*{organization_id}*"
        ]

        for pattern in patterns:
            self.cache_manager.delete_pattern(pattern)

    def invalidate_all_analytics(self, organization_id: int):
        """Invalidate all analytics caches for an organization"""
        patterns = [
            f"*org={organization_id}*",
            f"*{organization_id}*"
        ]

        for pattern in patterns:
            self.cache_manager.delete_pattern(pattern)

    def schedule_cache_refresh(self, organization_id: int):
        """
        Schedule a background cache refresh
        This should be called after invalidation to pre-populate the cache
        """
        # This would typically trigger a Celery task
        # For now, we'll just set a flag in Redis
        self.cache_manager.set(
            f"cache_refresh_pending:{organization_id}",
            "1",
            ttl=300  # 5 minutes
        )


def get_cache_invalidation_helper(cache_manager: CacheManager) -> CacheInvalidationHelper:
    """Factory function to get cache invalidation helper"""
    return CacheInvalidationHelper(cache_manager)
