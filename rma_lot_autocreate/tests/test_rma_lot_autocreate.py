# Copyright 2025 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.exceptions import ValidationError
from odoo.tests.common import Form

from odoo.addons.rma.tests.test_rma import TestRma


class TestRmaLotAutocreate(TestRma):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.operation.lot_sequence_id = cls.env.ref(
            "rma_lot_autocreate.seq_rma_lot_number"
        )
        cls.operation.auto_create_lot = True
        cls.product_tracked_lot = cls.env["product.product"].create(
            {
                "name": "Tracked by lot",
                "type": "product",
                "tracking": "lot",
            }
        )
        cls.product_tracked_serial = cls.env["product.product"].create(
            {
                "name": "Tracked by serial",
                "type": "product",
                "tracking": "serial",
            }
        )
        cls.product_untracked = cls.env["product.product"].create(
            {
                "name": "Untracked",
                "type": "product",
                "tracking": "none",
            }
        )

    def test_auto_creates_lot_on_confirm_for_lot_tracked(self):
        rma = self._create_rma(self.partner, self.product_tracked_lot)
        self.assertFalse(rma.lot_id)
        rma.action_confirm()
        self.assertTrue(rma.lot_id)
        self.assertEqual(rma.lot_id.product_id, self.product_tracked_lot)
        self.assertIn("RMA", rma.lot_id.name)

    def test_auto_creates_lot_on_confirm_for_serial_tracked(self):
        rma = self._create_rma(self.partner, self.product_tracked_serial)
        rma.action_confirm()
        self.assertTrue(rma.lot_id)
        self.assertIn("RMA", rma.lot_id.name)

    def test_does_nothing_if_flag_disabled(self):
        self.operation.auto_create_lot = False
        rma = self._create_rma(self.partner, self.product_tracked_lot)
        rma.action_confirm()
        self.assertFalse(rma.lot_id)

    def test_does_nothing_if_untracked(self):
        rma = self._create_rma(self.partner, self.product_untracked)
        rma.action_confirm()
        self.assertFalse(rma.lot_id)

    def test_does_nothing_if_existing_lot(self):
        existing_lot = self.env["stock.lot"].create(
            {"name": "EXISTING", "product_id": self.product_tracked_lot.id}
        )
        rma = self._create_rma(self.partner, self.product_tracked_lot)
        rma.lot_id = existing_lot
        rma.action_confirm()
        self.assertEqual(rma.lot_id, existing_lot)

    def test_operation_require_sequence(self):
        operation_form = Form(self.env["rma.operation"])
        operation_form.name = "OP"
        operation_form.auto_create_lot = True
        with self.assertRaisesRegexp(
            AssertionError, "lot_sequence_id is a required field.*"
        ):
            operation_form.save()
        operation = self.env["rma.operation"].create(
            {"name": "op", "auto_create_lot": False}
        )
        with self.assertRaisesRegexp(
            ValidationError,
            "You must set a Lot/Serial Name Sequence.*",
        ):
            operation.auto_create_lot = True
        with self.assertRaisesRegexp(
            ValidationError,
            "You must set a Lot/Serial Name Sequence.*",
        ):
            self.env["rma.operation"].create({"name": "op 2", "auto_create_lot": True})
