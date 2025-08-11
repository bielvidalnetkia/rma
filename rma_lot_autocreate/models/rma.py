# Copyright 2025 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class Rma(models.Model):

    _inherit = "rma"

    def action_confirm(self):
        for rma in self:
            rma._auto_create_lot_if_needed()
        return super().action_confirm()

    def _prepare_rma_lot_vals(self):
        return {
            "name": self.operation_id.lot_sequence_id.next_by_id(),
            "product_id": self.product_id.id,
            "company_id": self.company_id.id,
        }

    def _auto_create_lot_if_needed(self):
        self.ensure_one()
        if (
            not self.operation_id.auto_create_lot
            or not self.operation_id.lot_sequence_id
            or self.lot_id
            or self.product_id.tracking == "none"
        ):
            return None

        self.lot_id = self.env["stock.lot"].create(self._prepare_rma_lot_vals())
        return self.lot_id
