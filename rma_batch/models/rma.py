# Copyright 2025 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class Rma(models.Model):
    _inherit = "rma"

    batch_id = fields.Many2one(
        "rma.batch", string="RMA Batch", index=True, ondelete="cascade"
    )
    partner_id = fields.Many2one(
        compute="_compute_partner_id", store=True, readonly=False
    )
    user_id = fields.Many2one(compute="_compute_user_id", store=True, readonly=False)
    tag_ids = fields.Many2many(compute="_compute_tag_ids", store=True, readonly=False)

    @api.depends("batch_id.partner_id")
    def _compute_partner_id(self):
        for rec in self:
            if rec.batch_id.partner_id:
                rec.partner_id = rec.batch_id.partner_id

    @api.depends("batch_id.user_id")
    def _compute_user_id(self):
        for rec in self:
            if rec.batch_id.user_id:
                rec.user_id = rec.batch_id.user_id

    @api.depends("batch_id.tag_ids")
    def _compute_tag_ids(self):
        for rec in self:
            if rec.batch_id.tag_ids:
                rec.tag_ids = rec.batch_id.tag_ids

    @api.depends("user_id", "batch_id.team_id")
    def _compute_team_id(self):
        res = super()._compute_team_id()
        for rec in self:
            if rec.batch_id.team_id:
                rec.team_id = rec.batch_id.team_id
        return res
