from django.test import TestCase


class PageTests(TestCase):
    def test_primary_pages_render_with_navigation_and_content(self):
        pages = (
            ('/', 'Petopia — little joys for furry friends', 'Explore the shop'),
            ('/about/', 'Our story', 'We think pets'),
            ('/petshop/', 'The pet shop', 'Groom &amp;'),
        )

        for path, title, content in pages:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, title)
                self.assertContains(response, content)
                self.assertContains(response, 'aria-label="Main navigation"')
