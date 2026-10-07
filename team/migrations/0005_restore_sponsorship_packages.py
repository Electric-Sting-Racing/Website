from django.db import migrations


# Original sponsorship package; independent of the fictional demo dataset.
PACKAGES = (
    ("Bronze", "$500+", "Bronze Leaf", "1", "Extra small", False, False),
    ("Silver", "$1,500+", "Silver Tulip", "1", "Small", False, True),
    ("Gold", "$3,500+", "Gold Rose", "2", "Medium", True, True),
    ("Platinum", "$5,000+", "Platinum Orchid", "3", "Large", True, True),
)


def restore_packages(apps, schema_editor):
    tiers = apps.get_model("team", "SponsorshipTier").objects.using(schema_editor.connection.alias)
    for order, (name, amount, badge, posts, logo_size, tour, merch) in enumerate(PACKAGES):
        # Keep existing edits and intentionally disabled tiers intact. Avoid
        # get_or_create because older databases may contain duplicate names.
        if not tiers.filter(name__iexact=name).exists():
            tiers.create(name=name, amount=amount, badge=badge, social_posts=posts,
                         logo_size=logo_size, school_tour=tour, logo_on_merch=merch,
                         sort_order=order, active=True)


class Migration(migrations.Migration):
    dependencies = [("team", "0004_roster_sections")]
    operations = [migrations.RunPython(restore_packages, migrations.RunPython.noop)]
