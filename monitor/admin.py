from django.contrib import admin

from .models import ChangeEvent, Selector, Site, Snapshot


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ["name", "url", "check_interval_minutes", "created_at"]
    search_fields = ["name", "url"]


@admin.register(Selector)
class SelectorAdmin(admin.ModelAdmin):
    list_display = ["name", "site", "selector_type", "expected_type", "min_results", "is_active"]
    list_filter = ["selector_type", "expected_type", "is_active", "site"]
    search_fields = ["name", "selector"]
    list_editable = ["is_active"]


@admin.register(Snapshot)
class SnapshotAdmin(admin.ModelAdmin):
    list_display = ["selector", "status", "extracted_value", "checked_at"]
    list_filter = ["status", "selector__site"]
    readonly_fields = ["checked_at"]


@admin.register(ChangeEvent)
class ChangeEventAdmin(admin.ModelAdmin):
    list_display = ["selector", "change_type", "detected_at", "resolved"]
    list_filter = ["change_type", "resolved", "selector__site"]
    readonly_fields = ["detected_at", "resolved_at"]
    actions = ["mark_resolved"]

    @admin.action(description="Marcar como resolvido")
    def mark_resolved(self, request, queryset):
        from django.utils import timezone
        queryset.update(resolved=True, resolved_at=timezone.now())
