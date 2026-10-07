from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("team", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="SponsorshipTier",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=80)),
                ("amount", models.CharField(help_text="e.g. $500+", max_length=40)),
                ("badge", models.CharField(help_text="e.g. Bronze Leaf", max_length=80)),
                ("social_posts", models.CharField(default="1", max_length=20)),
                ("logo_size", models.CharField(default="Small", max_length=40)),
                ("school_tour", models.BooleanField(default=False)),
                ("logo_on_merch", models.BooleanField(default=False)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("active", models.BooleanField(default=True)),
            ],
            options={
                "ordering": ["sort_order", "name"],
                "verbose_name": "sponsorship tier",
                "verbose_name_plural": "sponsorship tiers",
            },
        ),
    ]

