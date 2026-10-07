from django.db import migrations, models


SECTION_MAP = {
    "battery": "high_voltage",
    "drivetrain": "powertrain",
    "controls": "low_voltage_controls",
}
NEW_SECTIONS = {"high_voltage", "powertrain", "low_voltage_controls", "frame", "suspensions"}


def assign_sections(apps, schema_editor):
    members = apps.get_model("team", "TeamMember").objects.using(schema_editor.connection.alias)
    old_values = list(members.order_by().values_list("subteam", flat=True).distinct())
    for old in old_values:
        if old and old not in NEW_SECTIONS:
            # Chassis formerly included frame AND suspension; do not guess a
            # student's new responsibility. Preserve all records for admin review.
            members.filter(subteam=old).update(previous_subteam=old, subteam=SECTION_MAP.get(old, ""))


def restore_sections(apps, schema_editor):
    members = apps.get_model("team", "TeamMember").objects.using(schema_editor.connection.alias)
    reverse_map = {new: old for old, new in SECTION_MAP.items()}
    reverse_map.update({"frame": "chassis", "suspensions": "chassis"})
    for member in members.all().iterator():
        member.subteam = member.previous_subteam or reverse_map.get(member.subteam, member.subteam)
        member.save(update_fields=["subteam"])


class Migration(migrations.Migration):
    dependencies = [("team", "0003_remove_article")]

    operations = [
        migrations.AddField(
            model_name="teammember", name="previous_subteam",
            field=models.CharField(blank=True, editable=False, max_length=24,
                help_text="Original section preserved during the five-section upgrade for reference."),
        ),
        migrations.AlterField(
            model_name="teammember", name="subteam",
            field=models.CharField("section", max_length=24, blank=True, default="",
                choices=[("high_voltage", "High Voltage"), ("powertrain", "Powertrain"),
                         ("low_voltage_controls", "Low Voltage/Controls"), ("frame", "Frame"),
                         ("suspensions", "Suspensions")],
                help_text="Choose a section to publish this member on the roster. Unassigned members remain in admin."),
        ),
        migrations.RunPython(assign_sections, restore_sections),
        migrations.AlterField(
            model_name="teammember", name="is_lead",
            field=models.BooleanField("section lead", default=False,
                help_text="Show a Section lead badge and list this member first. Multiple co-leads are supported."),
        ),
    ]
