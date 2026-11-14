from django import forms

from .models import Fighter


class FighterForm(forms.ModelForm):
    class Meta:
        model = Fighter
        fields = ["name", "unit_type", "team", "health", "attack_points", "profile_image_link"]
        labels = {
            "unit_type": "Type",
            "attack_points": "Attack points",
            "profile_image_link": "Profile image link",
        }
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Fighter name"}),
            "health": forms.NumberInput(attrs={"min": 0, "max": 100}),
            "attack_points": forms.NumberInput(attrs={"min": 0, "max": 50}),
            "profile_image_link": forms.URLInput(attrs={"placeholder": "https://example.com/fighter.jpg"}),
        }


class FightForm(forms.Form):
    first_fighter = forms.ModelChoiceField(queryset=Fighter.objects.none(), label="First fighter")
    second_fighter = forms.ModelChoiceField(queryset=Fighter.objects.none(), label="Second fighter")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        fighters = Fighter.objects.order_by("team", "name", "pk")
        self.fields["first_fighter"].queryset = fighters
        self.fields["second_fighter"].queryset = fighters

    def clean(self):
        cleaned_data = super().clean()
        first = cleaned_data.get("first_fighter")
        second = cleaned_data.get("second_fighter")
        if first and second:
            if first == second:
                raise forms.ValidationError("Choose two different fighters.")
            if first.team == second.team:
                raise forms.ValidationError("The selected fighters must be on different teams.")
            if first.health == 0 or second.health == 0:
                raise forms.ValidationError("Heal defeated fighters before starting another fight.")
        return cleaned_data
