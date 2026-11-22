from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import Profile


class ProfileTests(TestCase):
    def test_profile_is_linked_to_django_user(self):
        user = get_user_model().objects.create_user(username='petowner')
        profile = Profile.objects.create(
            user=user,
            phone_number='555-0100',
            address='12 Pet Street',
        )

        self.assertEqual(user.profile, profile)
        self.assertEqual(str(profile), 'petowner profile')
