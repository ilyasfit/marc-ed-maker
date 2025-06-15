import unittest
from bots.moderator_filters import contains_forbidden_link

class TestRegex(unittest.TestCase):

    def test_invalid_domain_not_flagged(self):
        message = "Viste a polyhedra network, caiu 80% hoje....na tua opiniao seria uma boa compra ?"
        whitelisted_domains = {"google.com"}
        self.assertFalse(contains_forbidden_link(message, whitelisted_domains))

    def test_valid_domain_flagged(self):
        message = "check out my new site mysite.com"
        whitelisted_domains = {"google.com"}
        self.assertTrue(contains_forbidden_link(message, whitelisted_domains))

    def test_whitelisted_domain_not_flagged(self):
        message = "check out google.com"
        whitelisted_domains = {"google.com"}
        self.assertFalse(contains_forbidden_link(message, whitelisted_domains))

if __name__ == '__main__':
    unittest.main()
