from django import forms

from .models import Selector, Site


class SiteForm(forms.ModelForm):
    class Meta:
        model = Site
        fields = ["name", "url", "check_interval_minutes"]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Ex: Books to Scrape"}
            ),
            "url": forms.URLInput(
                attrs={"class": "form-control", "placeholder": "https://exemplo.com"}
            ),
            "check_interval_minutes": forms.NumberInput(
                attrs={"class": "form-control", "min": 1}
            ),
        }
        labels = {
            "name": "Nome",
            "url": "URL alvo",
            "check_interval_minutes": "Intervalo (minutos)",
        }


class SelectorForm(forms.ModelForm):
    class Meta:
        model = Selector
        fields = ["name", "selector", "selector_type", "expected_type", "min_results", "anomaly_threshold", "is_active"]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Ex: Preço do produto"}
            ),
            "selector": forms.TextInput(
                attrs={
                    "class": "form-control font-monospace",
                    "placeholder": ".price_color ou //div[@class='price']",
                }
            ),
            "selector_type": forms.Select(attrs={"class": "form-select"}),
            "expected_type": forms.Select(attrs={"class": "form-select"}),
            "min_results": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "anomaly_threshold": forms.NumberInput(
                attrs={"class": "form-control", "min": 1, "max": 1000, "placeholder": "Ex: 20"}
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        labels = {
            "name": "Nome",
            "selector": "Seletor",
            "selector_type": "Tipo",
            "expected_type": "Dado esperado",
            "min_results": "Mínimo de resultados",
            "anomaly_threshold": "Alerta de variação (%)",
            "is_active": "Ativo",
        }
