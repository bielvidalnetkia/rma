# Copyright 2025 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RmaOperation(models.Model):

    _inherit = "rma.operation"

    auto_create_lot = fields.Boolean(
        string="Auto-create Lot/Serial on Confirm",
        help=(
            "If enabled, and the product is tracked and no lot/serial is set on the RMA, "
            "a new lot/serial will be created at confirmation."
        ),
    )

    lot_sequence_id = fields.Many2one(
        "ir.sequence",
        string="Lot/Serial Name Sequence",
        domain=[("code", "like", "rma.lot%")],
        help="Sequence used to generate names for auto-created lots/serials.",
    )

    @api.constrains("auto_create_lot", "lot_sequence_id")
    def _check_lot_sequence_required(self):
        for rec in self:
            if rec.auto_create_lot and not rec.lot_sequence_id:
                raise ValidationError(
                    _(
                        "You must set a Lot/Serial Name Sequence when Auto-create "
                        "Lot/Serial is enabled."
                    )
                )
