from django import forms


class ImportForm(forms.Form):
    kind = forms.ChoiceField(
        choices=[("invoice", "Invoices"), ("po", "Purchase orders"), ("receipt", "Receipts")]
    )
    file = forms.FileField(label="CSV file", help_text="UTF-8 · 256 KiB · 500 rows maximum")


class ResolutionForm(forms.Form):
    revision = forms.IntegerField(widget=forms.HiddenInput)
    note = forms.CharField(
        label="Reviewer resolution",
        max_length=2000,
        widget=forms.Textarea(
            attrs={"rows": 3, "placeholder": "Explain why the listed discrepancies are accepted."}
        ),
    )
