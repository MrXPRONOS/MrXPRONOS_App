"""Unit checks for sanitized post-repair ownership classifications."""
import unittest
from types import SimpleNamespace as Obj
from scripts.telegram_owner_readonly_postrepair import (
    own_permissions, bot_permissions, Inventory,
)


class InventorySafetyTests(unittest.TestCase):
    def test_owner_rights_classes(self):
        self.assertEqual(own_permissions(Obj(is_creator=True)), "creator")
        self.assertEqual(own_permissions(Obj(is_admin=True, add_admins=True)), "admin_promote")
        self.assertEqual(own_permissions(Obj(is_admin=True, add_admins=False)), "admin_no_promote")
        self.assertEqual(own_permissions(Obj(is_admin=False)), "not_admin")

    def test_bot_post_rights_classes(self):
        self.assertEqual(bot_permissions(Obj(is_admin=True, post_messages=True)), "admin_post")
        self.assertEqual(bot_permissions(Obj(is_admin=True, post_messages=False)), "admin_no_post")
        self.assertEqual(bot_permissions(Obj(is_admin=False)), "not_admin")

    def test_inventory_exposes_only_fixed_status_fields(self):
        keys = set(vars(Inventory()))
        self.assertEqual(keys, {
            "session", "stage_reference", "stage_existing", "stage_owner",
            "stage_bot", "crypto_resolved", "crypto_owner", "crypto_bot"
        })


if __name__ == "__main__":
    unittest.main()
