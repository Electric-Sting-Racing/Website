from django.db import migrations


def normalize_bronze_description(apps, schema_editor):
    tiers = apps.get_model("team", "SponsorshipTier").objects.using(schema_editor.connection.alias)
    # SQLite databases may have applied the original 0007 despite its
    # overlong value. Update that exact default; preserve editorial changes.
    tiers.filter(
        name__iexact="Bronze",
        logo_size="Extra small in a secondary bodywork location",
    ).update(logo_size="Extra small on secondary bodywork")


class Migration(migrations.Migration):
    dependencies = [("team", "0007_requested_leads_and_proposal_benefits")]
    operations = [migrations.RunPython(normalize_bronze_description, migrations.RunPython.noop)]
