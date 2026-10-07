from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from team.models import Car, Event, Sponsor, SponsorshipTier, TeamMember


class Command(BaseCommand):
    help = "Load a small Electric Sting Racing demo dataset for the website."

    @transaction.atomic
    def handle(self, *args, **options):
        members = [
            ("Maya Chen", "Frame Lead", "frame", "Class of 2027", True),
            ("Arjun Patel", "High Voltage Lead", "high_voltage", "Class of 2026", True),
            ("Nora Williams", "Controls Lead", "low_voltage_controls", "Class of 2027", True),
            ("Theo Martin", "Suspensions Lead", "suspensions", "Class of 2028", True),
            ("Sam Rivera", "Powertrain Lead", "powertrain", "Class of 2027", True),
            ("Priya Shah", "Frame Design", "frame", "Class of 2028", False),
            ("Eli Brooks", "Battery Systems", "high_voltage", "Class of 2029", False),
            ("Quinn Foster", "Embedded Software", "low_voltage_controls", "Class of 2028", False),
            ("Jordan Lee", "Drivetrain Design", "powertrain", "Class of 2029", False),
            ("Camila Ortiz", "Suspension Design", "suspensions", "Class of 2028", False),
        ]
        for order, (name, role, subteam, year, is_lead) in enumerate(members):
            TeamMember.objects.update_or_create(
                name=name,
                defaults={
                    "role": role,
                    "subteam": subteam,
                    "year": year,
                    "is_lead": is_lead,
                    "active": True,
                    "sort_order": order,
                    "bio": "Designing, testing, and learning as part of Sacramento State's first electric Formula SAE team.",
                },
            )

        Car.objects.update_or_create(
            slug="electric-sting-27",
            defaults={
                "name": "ELECTRIC STING 01",
                "season": "2027",
                "tagline": "Our first car. Still in design.",
                "description": "Our first electric formula car has not been built yet. We are developing the design and preparing for manufacturing, assembly, and testing.",
                "image_url": "",
                "top_speed": "TBD in testing",
                "acceleration": "TBD in testing",
                "peak_power": "Engineering target",
                "accumulator": "In design",
                "chassis": "In design",
                "featured": True,
                "is_current": True,
            },
        )

        events = [
            ("Campus launch night", date.today() + timedelta(days=16), "6:00 PM", "Sacramento State Engineering"),
            ("Subsystem design review", date.today() + timedelta(days=29), "6:00 PM", "Engineering & Computer Science 101"),
            ("Recruitment workshop", date.today() + timedelta(days=44), "7:00 PM", "Sacramento State Makerspace"),
        ]
        for title, event_date, event_time, location in events:
            Event.objects.update_or_create(
                title=title,
                defaults={
                    "date": event_date,
                    "time": event_time,
                    "location": location,
                    "description": "Open to students, alumni, and friends of Electric Sting Racing.",
                    "is_public": True,
                },
            )

        sponsors = [
            ("Your company", "champion"),
            ("Sac State Engineering", "builder"),
            ("Student Alumni Network", "partner"),
        ]
        for order, (name, tier) in enumerate(sponsors):
            Sponsor.objects.update_or_create(
                name=name,
                defaults={
                    "tier": tier,
                    "description": "Helping Sacramento State build its first electric Formula SAE car.",
                    "sort_order": order,
                    "active": True,
                },
            )

        tiers = [
            ("Bronze", "$500+", "Bronze Leaf", "1", "Extra small", False, False),
            ("Silver", "$1,500+", "Silver Tulip", "1", "Small", False, True),
            ("Gold", "$3,500+", "Gold Rose", "2", "Medium", True, True),
            ("Platinum", "$5,000+", "Platinum Orchid", "3", "Large", True, True),
        ]
        for order, (name, amount, badge, posts, logo_size, school_tour, logo_on_merch) in enumerate(tiers):
            SponsorshipTier.objects.update_or_create(
                name=name,
                defaults={
                    "amount": amount,
                    "badge": badge,
                    "social_posts": posts,
                    "logo_size": logo_size,
                    "school_tour": school_tour,
                    "logo_on_merch": logo_on_merch,
                    "sort_order": order,
                    "active": True,
                },
            )

        self.stdout.write(self.style.SUCCESS("Electric Sting demo content loaded. Create an admin user with `python manage.py createsuperuser`."))
