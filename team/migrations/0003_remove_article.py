from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("team", "0002_sponsorshiptier"),
    ]

    operations = [
        migrations.DeleteModel(
            name="Article",
        ),
    ]
