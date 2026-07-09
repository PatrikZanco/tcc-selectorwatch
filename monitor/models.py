from django.db import models


class Site(models.Model):
    name = models.CharField("Nome", max_length=200)
    url = models.URLField("URL alvo", unique=True)
    check_interval_minutes = models.PositiveIntegerField(
        "Intervalo de verificação (min)", default=60
    )
    created_at = models.DateTimeField("Criado em", auto_now_add=True)

    class Meta:
        verbose_name = "Site"
        verbose_name_plural = "Sites"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Selector(models.Model):
    CSS = "css"
    XPATH = "xpath"
    SELECTOR_TYPES = [(CSS, "CSS"), (XPATH, "XPath")]

    TEXT = "text"
    NUMBER = "number"
    URL = "url"
    ANY = "any"
    EXPECTED_TYPES = [
        (TEXT, "Texto"),
        (NUMBER, "Número"),
        (URL, "URL"),
        (ANY, "Qualquer"),
    ]

    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="selectors")
    name = models.CharField("Nome", max_length=200)
    selector = models.TextField("Seletor")
    selector_type = models.CharField(
        "Tipo", max_length=10, choices=SELECTOR_TYPES, default=CSS
    )
    expected_type = models.CharField(
        "Tipo de dado esperado", max_length=10, choices=EXPECTED_TYPES, default=ANY
    )
    min_results = models.PositiveIntegerField("Mínimo de resultados", default=1)
    anomaly_threshold = models.PositiveIntegerField(
        "Alerta de variação (%)", null=True, blank=True,
        help_text="Gera alerta se o valor numérico variar mais que X% em relação à última leitura. Deixe vazio para desativar."
    )
    is_active = models.BooleanField("Ativo", default=True)
    created_at = models.DateTimeField("Criado em", auto_now_add=True)

    class Meta:
        verbose_name = "Seletor"
        verbose_name_plural = "Seletores"
        ordering = ["site", "name"]

    def __str__(self):
        return f"{self.site.name} / {self.name}"

    @property
    def last_snapshot(self):
        return self.snapshots.order_by("-checked_at").first()

    @property
    def last_status(self):
        snap = self.last_snapshot
        return snap.status if snap else None

    @property
    def pending_events_count(self):
        return self.change_events.filter(resolved=False).count()


class Snapshot(models.Model):
    OK = "ok"
    FAILED = "failed"
    STATUS_CHOICES = [(OK, "OK"), (FAILED, "Falhou")]

    SELECTOR_EMPTY = "selector_empty"
    HTTP_ERROR = "http_error"
    NETWORK_ERROR = "network_error"
    TYPE_MISMATCH = "type_mismatch"
    FAILURE_REASONS = [
        (SELECTOR_EMPTY, "Seletor sem resultados"),
        (HTTP_ERROR, "Erro HTTP (4xx/5xx)"),
        (NETWORK_ERROR, "Erro de rede/conexão"),
        (TYPE_MISMATCH, "Tipo de dado incorreto"),
    ]

    selector = models.ForeignKey(
        Selector, on_delete=models.CASCADE, related_name="snapshots"
    )
    html_fragment = models.TextField("Fragmento HTML", blank=True)
    extracted_value = models.TextField("Valor extraído", blank=True)
    status = models.CharField("Status", max_length=10, choices=STATUS_CHOICES)
    failure_reason = models.CharField(
        "Motivo da falha", max_length=20, blank=True, choices=FAILURE_REASONS
    )
    checked_at = models.DateTimeField("Verificado em", auto_now_add=True)

    class Meta:
        verbose_name = "Snapshot"
        verbose_name_plural = "Snapshots"
        ordering = ["-checked_at"]

    def __str__(self):
        return f"{self.selector} [{self.status}] {self.checked_at:%Y-%m-%d %H:%M}"


class ChangeEvent(models.Model):
    selector = models.ForeignKey(
        Selector, on_delete=models.CASCADE, related_name="change_events"
    )
    detected_at = models.DateTimeField("Detectado em", auto_now_add=True)
    change_type = models.CharField("Tipo de mudança", max_length=60, blank=True)
    old_html_fragment = models.TextField("HTML anterior", blank=True)
    new_html_fragment = models.TextField("HTML atual", blank=True)
    diff_report = models.TextField("Diff", blank=True)
    suggested_selectors = models.JSONField("Sugestões do LLM", null=True, blank=True)
    validation_results = models.JSONField(
        "Resultados de validação", null=True, blank=True
    )
    resolved = models.BooleanField("Resolvido", default=False)
    resolved_at = models.DateTimeField("Resolvido em", null=True, blank=True)
    auto_healed = models.BooleanField("Curado automaticamente", default=False)
    applied_selector = models.TextField("Seletor aplicado", blank=True)

    class Meta:
        verbose_name = "Evento de falha"
        verbose_name_plural = "Eventos de falha"
        ordering = ["-detected_at"]

    def __str__(self):
        return f"{self.selector} — {self.change_type} — {self.detected_at:%Y-%m-%d %H:%M}"
