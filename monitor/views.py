import datetime
import difflib
import json

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from .forms import SelectorForm, SiteForm
from .models import ChangeEvent, Selector, Site, Snapshot


class DashboardView(View):
    def get(self, request):
        site_id = request.GET.get("site")
        now = timezone.now()
        last_24h = now - datetime.timedelta(hours=24)
        last_7d = now - datetime.timedelta(days=7)

        sites = Site.objects.all()
        selectors = Selector.objects.filter(is_active=True).select_related("site")
        if site_id:
            selectors = selectors.filter(site_id=site_id)

        data = []
        for sel in selectors:
            last_snap = sel.snapshots.order_by("-checked_at").first()
            pending = sel.change_events.filter(resolved=False).count()
            snaps_7d = sel.snapshots.filter(checked_at__gte=last_7d)
            total_7d = snaps_7d.count()
            ok_7d = snaps_7d.filter(status="ok").count()
            uptime_7d = round(ok_7d / total_7d * 100) if total_7d > 0 else None
            data.append({
                "selector": sel,
                "last_snapshot": last_snap,
                "pending_events": pending,
                "total_7d": total_7d,
                "ok_7d": ok_7d,
                "uptime_7d": uptime_7d,
            })

        snap_qs = Snapshot.objects.all()
        event_qs = ChangeEvent.objects.all()
        if site_id:
            snap_qs = snap_qs.filter(selector__site_id=site_id)
            event_qs = event_qs.filter(selector__site_id=site_id)

        checks_24h = snap_qs.filter(checked_at__gte=last_24h).count()
        ok_24h = snap_qs.filter(checked_at__gte=last_24h, status="ok").count()
        success_rate_24h = round(ok_24h / checks_24h * 100) if checks_24h else None

        active_failures = event_qs.filter(resolved=False).exclude(change_type="anomalia_de_valor").count()
        anomalies_7d = event_qs.filter(change_type="anomalia_de_valor", detected_at__gte=last_7d).count()

        resolved = list(
            event_qs.filter(resolved=True, resolved_at__isnull=False)
            .exclude(change_type="anomalia_de_valor")
            .values_list("detected_at", "resolved_at")
        )
        if resolved:
            avg_secs = sum((r - d).total_seconds() for d, r in resolved) / len(resolved)
            mttr_hours = round(avg_secs / 3600, 1)
        else:
            mttr_hours = None

        failures_by_reason = (
            snap_qs.filter(checked_at__gte=last_24h, status="failed")
            .exclude(failure_reason="")
            .values("failure_reason")
            .annotate(total=Count("id"))
            .order_by("-total")
        )
        reason_labels = dict(Snapshot.FAILURE_REASONS)
        failures_detail = [
            {"label": reason_labels.get(r["failure_reason"], r["failure_reason"]), "total": r["total"]}
            for r in failures_by_reason
        ]

        selectors_with_fail = (
            Snapshot.objects.filter(selector__in=selectors, status="failed")
            .values("selector_id").distinct().count()
        )
        selectors_with_events_ct = (
            ChangeEvent.objects.filter(selector__in=selectors)
            .values("selector_id").distinct().count()
        )
        recall = (
            round(selectors_with_events_ct / selectors_with_fail * 100)
            if selectors_with_fail else None
        )

        total_val = 0
        success_val = 0
        for ev in event_qs.filter(validation_results__isnull=False):
            for v in (ev.validation_results or []):
                total_val += 1
                if v.get("works"):
                    success_val += 1
        llm_accuracy = round(success_val / total_val * 100) if total_val else None

        events_with_valid = 0
        for ev in event_qs.filter(validation_results__isnull=False):
            if any(v.get("works") for v in (ev.validation_results or [])):
                events_with_valid += 1
        total_events = event_qs.count()
        auto_recovery_rate = round(events_with_valid / total_events * 100) if total_events else None

        manual_mttr_hours = 24.0
        time_saved = (
            round((manual_mttr_hours - mttr_hours) * total_events, 1)
            if mttr_hours is not None and total_events > 0 else None
        )

        total_checks_alltime = snap_qs.count()
        ok_alltime = snap_qs.filter(status="ok").count()
        overall_uptime = round(ok_alltime / total_checks_alltime * 100, 1) if total_checks_alltime else None
        total_sites = Site.objects.count()
        total_selectors_active = selectors.count()


        days_iso = [
            (now.date() - datetime.timedelta(days=i)).isoformat()
            for i in range(6, -1, -1)
        ]
        ok_map = {d: 0 for d in days_iso}
        fail_map = {d: 0 for d in days_iso}
        for row in (
            snap_qs.filter(checked_at__gte=last_7d)
            .annotate(day=TruncDate("checked_at"))
            .values("day", "status")
            .annotate(n=Count("id"))
        ):
            dstr = row["day"].isoformat() if hasattr(row["day"], "isoformat") else str(row["day"])
            if dstr in ok_map:
                if row["status"] == "ok":
                    ok_map[dstr] += row["n"]
                else:
                    fail_map[dstr] += row["n"]

        _ct_labels = {
            "renomeacao_de_classe_css": "Renomeação CSS",
            "elemento_removido": "Elem. Removido",
            "tag_removida": "Tag Removida",
            "estrutura_adicionada": "Estrutura Nova",
            "conteudo_alterado": "Conteúdo Alterado",
            "anomalia_de_valor": "Anomalia de Valor",
            "desconhecido": "Desconhecido",
        }
        change_rows = list(
            event_qs.values("change_type")
            .annotate(total=Count("id"))
            .order_by("-total")
        )

        sorted_data = sorted(data, key=lambda x: (x["uptime_7d"] if x["uptime_7d"] is not None else -1))
        sel_names = [item["selector"].name for item in sorted_data if item["uptime_7d"] is not None]
        sel_uptimes = [item["uptime_7d"] for item in sorted_data if item["uptime_7d"] is not None]

        checks_per_sel = list(
            snap_qs.values("selector__name")
            .annotate(n=Count("id"))
            .order_by("-n")
        )

        type_counts = {}
        for sel in selectors:
            t = sel.get_selector_type_display()
            type_counts[t] = type_counts.get(t, 0) + 1

        total_ok_count = sum(1 for d in data if d["last_snapshot"] and d["last_snapshot"].status == "ok")
        total_failed_count = sum(1 for d in data if d["last_snapshot"] and d["last_snapshot"].status == "failed")
        total_no_data_count = sum(1 for d in data if not d["last_snapshot"])

        context = {
            "data": data,
            "sites": sites,
            "selected_site_id": site_id,
            "total_ok": total_ok_count,
            "total_failed": total_failed_count,
            "total_no_data": total_no_data_count,
            "checks_24h": checks_24h,
            "success_rate_24h": success_rate_24h,
            "active_failures": active_failures,
            "anomalies_7d": anomalies_7d,
            "mttr_hours": mttr_hours,
            "failures_detail": failures_detail,
            "total_sites": total_sites,
            "total_selectors_active": total_selectors_active,
            "total_checks_alltime": total_checks_alltime,
            "overall_uptime": overall_uptime,
            "recall": recall,
            "llm_accuracy": llm_accuracy,
            "auto_recovery_rate": auto_recovery_rate,
            "manual_mttr_hours": manual_mttr_hours,
            "time_saved": time_saved,
            "total_events": total_events,
            "chart_status": json.dumps([total_ok_count, total_failed_count, total_no_data_count]),
            "chart_days": json.dumps([d[5:] for d in days_iso]),
            "chart_ok": json.dumps([ok_map[d] for d in days_iso]),
            "chart_failed": json.dumps([fail_map[d] for d in days_iso]),
            "chart_change_labels": json.dumps(
                [_ct_labels.get(r["change_type"], r["change_type"]) for r in change_rows]
            ),
            "chart_change_values": json.dumps([r["total"] for r in change_rows]),
            "chart_sel_names": json.dumps(sel_names),
            "chart_sel_uptimes": json.dumps(sel_uptimes),
            "chart_checks_sel_labels": json.dumps([r["selector__name"] for r in checks_per_sel]),
            "chart_checks_sel_values": json.dumps([r["n"] for r in checks_per_sel]),
            "chart_type_labels": json.dumps(list(type_counts.keys())),
            "chart_type_values": json.dumps(list(type_counts.values())),
            "chart_recall": json.dumps(recall),
            "chart_llm_accuracy": json.dumps(llm_accuracy),
            "chart_auto_recovery": json.dumps(auto_recovery_rate),
        }
        return render(request, "dashboard.html", context)


class EventListView(View):
    def get(self, request):
        site_id = request.GET.get("site")
        resolved = request.GET.get("resolved", "0")
        sites = Site.objects.all()

        events = ChangeEvent.objects.select_related("selector__site").order_by("-detected_at")
        if site_id:
            events = events.filter(selector__site_id=site_id)
        if resolved == "1":
            events = events.filter(resolved=True)
        else:
            events = events.filter(resolved=False)

        paginator = Paginator(events, 25)
        page = paginator.get_page(request.GET.get("page", 1))

        return render(
            request,
            "event_list.html",
            {
                "page_obj": page,
                "sites": sites,
                "selected_site_id": site_id,
                "show_resolved": resolved == "1",
            },
        )


class EventDetailView(View):
    def get(self, request, pk):
        event = get_object_or_404(
            ChangeEvent.objects.select_related("selector__site"), pk=pk
        )

        diff_html = None
        if event.old_html_fragment and event.new_html_fragment:
            d = difflib.HtmlDiff(wrapcolumn=90)
            diff_html = d.make_table(
                event.old_html_fragment.splitlines(),
                event.new_html_fragment.splitlines(),
                fromdesc="HTML anterior (seletor funcionava)",
                todesc="HTML atual (seletor falhou)",
            )

        return render(
            request,
            "event_detail.html",
            {"event": event, "diff_html": diff_html},
        )

    def post(self, request, pk):
        event = get_object_or_404(ChangeEvent, pk=pk)
        event.resolved = True
        event.resolved_at = timezone.now()
        event.save()
        messages.success(request, "Evento marcado como resolvido.")
        return redirect("event_detail", pk=pk)


class HistoryView(View):
    def get(self, request):
        selector_id = request.GET.get("selector")
        selectors = Selector.objects.select_related("site").filter(is_active=True)

        snapshots = Snapshot.objects.select_related("selector__site").order_by("-checked_at")
        if selector_id:
            snapshots = snapshots.filter(selector_id=selector_id)

        paginator = Paginator(snapshots, 50)
        page = paginator.get_page(request.GET.get("page", 1))

        return render(
            request,
            "history.html",
            {
                "page_obj": page,
                "selectors": selectors,
                "selected_selector_id": selector_id,
            },
        )



class SiteListView(View):
    def get(self, request):
        sites = Site.objects.prefetch_related("selectors").order_by("name")
        form = SiteForm()
        return render(request, "sites.html", {"sites": sites, "form": form})

    def post(self, request):
        form = SiteForm(request.POST)
        if form.is_valid():
            site = form.save()
            messages.success(request, f'Site "{site.name}" criado com sucesso.')
            return redirect("site_detail", pk=site.pk)
        sites = Site.objects.prefetch_related("selectors").order_by("name")
        return render(request, "sites.html", {"sites": sites, "form": form})


class SiteDetailView(View):
    def get(self, request, pk):
        site = get_object_or_404(Site, pk=pk)
        selectors = site.selectors.order_by("name")
        form = SiteForm(instance=site)
        selector_form = SelectorForm()
        return render(
            request,
            "site_detail.html",
            {"site": site, "selectors": selectors, "form": form, "selector_form": selector_form},
        )

    def post(self, request, pk):
        site = get_object_or_404(Site, pk=pk)
        form = SiteForm(request.POST, instance=site)
        if form.is_valid():
            form.save()
            messages.success(request, "Site atualizado.")
            return redirect("site_detail", pk=pk)
        selectors = site.selectors.order_by("name")
        selector_form = SelectorForm()
        return render(
            request,
            "site_detail.html",
            {"site": site, "selectors": selectors, "form": form, "selector_form": selector_form},
        )


class SiteDeleteView(View):
    def post(self, request, pk):
        site = get_object_or_404(Site, pk=pk)
        name = site.name
        site.delete()
        messages.success(request, f'Site "{name}" removido.')
        return redirect("site_list")



class SelectorCreateView(View):
    def post(self, request, site_pk):
        site = get_object_or_404(Site, pk=site_pk)
        form = SelectorForm(request.POST)
        if form.is_valid():
            sel = form.save(commit=False)
            sel.site = site
            sel.save()
            messages.success(request, f'Seletor "{sel.name}" adicionado.')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
        return redirect("site_detail", pk=site_pk)


class SelectorEditView(View):
    def get(self, request, pk):
        sel = get_object_or_404(Selector.objects.select_related("site"), pk=pk)
        form = SelectorForm(instance=sel)
        return render(request, "selector_form.html", {"sel": sel, "form": form})

    def post(self, request, pk):
        sel = get_object_or_404(Selector.objects.select_related("site"), pk=pk)
        form = SelectorForm(request.POST, instance=sel)
        if form.is_valid():
            form.save()
            messages.success(request, "Seletor atualizado.")
            return redirect("site_detail", pk=sel.site_id)
        return render(request, "selector_form.html", {"sel": sel, "form": form})


class SelectorDeleteView(View):
    def post(self, request, pk):
        sel = get_object_or_404(Selector, pk=pk)
        site_pk = sel.site_id
        name = sel.name
        sel.delete()
        messages.success(request, f'Seletor "{name}" removido.')
        return redirect("site_detail", pk=site_pk)
