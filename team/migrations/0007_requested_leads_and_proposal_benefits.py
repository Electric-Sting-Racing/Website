from django.db import migrations


LEADS = (
    ("Mizael Iniguez", "business", "Business Lead"),
    ("Mirzett Evans IV", "high_voltage", "High Voltage Lead"),
    ("Ben Israel Gurjar", "powertrain", "Powertrain Lead"),
    ("Micheal Quezada", "powertrain", "Powertrain Lead"),
    ("Juan Magana", "powertrain", "Powertrain Lead"),
    ("Branden Pavon", "low_voltage_controls", "Low Voltage/Controls Lead"),
    ("Jay Tolentino", "low_voltage_controls", "Low Voltage/Controls Lead"),
    ("Sergio Torres Guzman", "frame", "Frame Lead"),
    ("Jacqueline Garcia", "suspensions", "Suspension Lead"),
)

# Benefits transcribed from page 8 of the supplied 2026–2027 proposal.
BENEFITS = {
    "Bronze": {
        "website_recognition": "Small logo + company website link",
        "social_media_recognition": "1 story announcement",
        "progress_updates": "No",
        "event_invitations": "No",
        "recruiting": "Recruiting opportunities",
        "merchandise": "Logo on merchandise",
    },
    "Silver": {
        "website_recognition": "Medium logo + company website link",
        "social_media_recognition": "1 story announcement",
        "progress_updates": "Post-season summary",
        "event_invitations": "Yes",
        "recruiting": "Resume sending",
        "merchandise": "Logo on merchandise + free sticker",
    },
    "Gold": {
        "website_recognition": "Large logo + company website link",
        "social_media_recognition": "1 story announcement + 1 post",
        "progress_updates": "Fall and spring",
        "event_invitations": "Yes, and exclusive showings",
        "recruiting": "Resume upload and networking event",
        "merchandise": "Logo on merchandise + free keychain",
    },
    "Platinum": {
        "website_recognition": "Large logo + company website link + homepage placement",
        "social_media_recognition": "1 story announcement + 1 post",
        "progress_updates": "Monthly progress check-ins",
        "event_invitations": "Yes, exclusive meetings and private engineering presentations",
        "recruiting": "Direct networking and resume uploads",
        "merchandise": "Logo on merchandise + free T-shirt",
    },
}
CAR_LOGOS = {
    "Bronze": ("Extra small", "Extra small on secondary bodywork"),
    "Silver": ("Small", "Small secondary bodywork location"),
    "Gold": ("Medium", "Medium, visible side or front bodywork"),
    "Platinum": ("Large", "Large premium car location"),
}


def add_requested_content(apps, schema_editor):
    members = apps.get_model("team", "TeamMember").objects.using(schema_editor.connection.alias)
    for order, (name, section, role) in enumerate(LEADS):
        # Reuse the existing profile without replacing bio, photo, or class year.
        existing = members.filter(name__iexact=name).order_by("pk")
        values = {"subteam": section, "role": role, "is_lead": True, "active": True, "sort_order": order}
        if existing.exists():
            existing.update(**values)
        else:
            members.create(name=name, **values)

    tiers = apps.get_model("team", "SponsorshipTier").objects.using(schema_editor.connection.alias)
    for name, benefits in BENEFITS.items():
        for tier in tiers.filter(name__iexact=name):
            changed = []
            for field, value in benefits.items():
                if not getattr(tier, field):
                    setattr(tier, field, value)
                    changed.append(field)
            old_logo, new_logo = CAR_LOGOS[name]
            if tier.logo_size == old_logo:
                tier.logo_size = new_logo
                changed.append("logo_size")
            # The current proposal includes Bronze merchandise recognition.
            if name == "Bronze" and tier.amount == "$500+" and tier.badge == "Bronze Leaf":
                tier.logo_on_merch = True
                changed.append("logo_on_merch")
            if changed:
                tier.save(update_fields=changed)


class Migration(migrations.Migration):
    dependencies = [("team", "0006_sponsorshiptier_event_invitations_and_more")]
    operations = [migrations.RunPython(add_requested_content, migrations.RunPython.noop)]
