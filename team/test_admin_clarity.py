from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from .models import Car, GalleryImage, Sponsor, TeamMember

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


def make_car(slug, **overrides):
    data = {"name": slug.upper(), "season": "2027", "slug": slug, "tagline": "t", "description": "d"}
    data.update(overrides)
    return Car.objects.create(**data)


class CurrentCarTests(TestCase):
    def test_marking_a_car_current_clears_the_others(self):
        old = make_car("es-01", is_current=True)
        new = make_car("es-02", is_current=True)
        old.refresh_from_db()
        self.assertFalse(old.is_current)
        self.assertTrue(new.is_current)

    def test_saving_a_non_current_car_leaves_the_current_one_alone(self):
        current = make_car("es-01", is_current=True)
        make_car("es-02")
        current.refresh_from_db()
        self.assertTrue(current.is_current)

    def test_partial_save_of_a_stale_copy_does_not_unset_the_real_current_car(self):
        stale = make_car("es-01", is_current=True)
        winner = make_car("es-02", is_current=True)
        stale.name = "Renamed"
        stale.save(update_fields=["name"])
        winner.refresh_from_db()
        self.assertTrue(winner.is_current)
        self.assertEqual(Car.objects.filter(is_current=True).count(), 1)

    def test_partial_save_including_the_flag_still_enforces_one_current(self):
        first = make_car("es-01", is_current=True)
        second = make_car("es-02")
        second.is_current = True
        second.save(update_fields=["is_current"])
        first.refresh_from_db()
        self.assertFalse(first.is_current)

    def test_resaving_the_current_car_keeps_it_current(self):
        car = make_car("es-01", is_current=True)
        car.name = "Renamed"
        car.save()
        car.refresh_from_db()
        self.assertTrue(car.is_current)
        self.assertEqual(Car.objects.filter(is_current=True).count(), 1)


@override_settings(STORAGES=STORAGES)
class AdminClarityTests(TestCase):
    def setUp(self):
        admin = get_user_model().objects.create_superuser("root", password="long-root-password")
        self.client.force_login(admin)

    def test_car_can_be_added_without_the_fields_the_site_does_not_show(self):
        response = self.client.post("/admin/team/car/add/", {
            "name": "ES 03", "season": "2028", "slug": "es-03", "is_current": "on",
            "tagline": "", "description": "",
        })
        self.assertEqual(response.status_code, 302)
        car = Car.objects.get(slug="es-03")
        self.assertEqual((car.tagline, car.description), ("", ""))

    def test_car_form_separates_shown_fields_from_unused_ones(self):
        html = self.client.get("/admin/team/car/add/").content.decode()
        self.assertIn("Shown on the website", html)
        self.assertIn("Kept for later (not shown yet)", html)
        self.assertLess(html.index("Shown on the website"), html.index("Kept for later"))

    def test_tier_form_labels_table_rows_and_unused_fields(self):
        html = self.client.get("/admin/team/sponsorshiptier/add/").content.decode()
        self.assertIn("Rows in the sponsorship comparison table", html)
        self.assertIn("Kept for later (not shown yet)", html)

    def test_archiving_members_hides_them_from_the_roster(self):
        member = TeamMember.objects.create(name="Sam Rivera", role="Driver", subteam="powertrain")
        self.assertContains(self.client.get("/team/"), "Sam Rivera")
        self.client.post("/admin/team/teammember/", {"action": "archive_members", "_selected_action": [member.pk]})
        member.refresh_from_db()
        self.assertFalse(member.active)
        self.assertNotContains(self.client.get("/team/"), "Sam Rivera")
        self.client.post("/admin/team/teammember/", {"action": "restore_members", "_selected_action": [member.pk]})
        member.refresh_from_db()
        self.assertTrue(member.active)

    def test_sponsors_can_be_hidden_in_bulk_and_list_shows_logos(self):
        sponsor = Sponsor.objects.create(
            name="Acme", description="Parts", logo_url="https://example.com/acme.png",
        )
        self.assertContains(self.client.get("/admin/team/sponsor/"), 'src="https://example.com/acme.png"')
        self.client.post("/admin/team/sponsor/", {"action": "hide_from_site", "_selected_action": [sponsor.pk]})
        sponsor.refresh_from_db()
        self.assertFalse(sponsor.active)

    def test_gallery_list_shows_thumbnails(self):
        GalleryImage.objects.create(title="Shop", image_url="https://example.com/shop.jpg", alt_text="The shop")
        self.assertContains(self.client.get("/admin/team/galleryimage/"), 'src="https://example.com/shop.jpg"')

    def test_admin_uses_plain_language_titles(self):
        self.assertContains(self.client.get("/admin/"), "Edit the team website")
