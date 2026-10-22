from django.db import migrations


def add_tesla(apps, schema_editor):
    sponsors = apps.get_model("team", "Sponsor").objects.using(schema_editor.connection.alias)
    # get_or_create: never overwrite a Tesla row that was already set up or edited in /admin/.
    sponsors.get_or_create(
        name="Tesla",
        defaults={
            "tier": "champion",
            "website": "https://www.tesla.com",
            "description": "Champion sponsor of Sacramento State's first electric Formula SAE car.",
            "sort_order": 0,
            "active": True,
        },
    )


class Migration(migrations.Migration):
    dependencies = [("team", "0008_normalize_bronze_logo_description")]
    operations = [migrations.RunPython(add_tesla, migrations.RunPython.noop)]
