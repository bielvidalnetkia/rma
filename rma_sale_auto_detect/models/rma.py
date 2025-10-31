# Copyright 2025 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from collections import defaultdict
from datetime import timedelta

from odoo import _, api, fields, models


class Rma(models.Model):
    _inherit = "rma"
    has_sale_auto_detect_issue = fields.Boolean(readonly=True)
    ignore_sale_auto_detect = fields.Boolean(readonly=True)
    sale_auto_detect_note = fields.Text(readonly=True)

    def action_link_rma_to_sale_line(self):
        """automatically link RMAs to the most relevant sale order lines"""
        self.write(
            {"has_sale_auto_detect_issue": False, "sale_auto_detect_note": False}
        )
        rma_to_link = self.filtered(
            lambda r: not r.sale_line_id and not r.ignore_sale_auto_detect
        )
        for rmas, sale_lines in rma_to_link._map_rmas_to_sale_lines().items():
            rmas._link_rma_to_sale_line(sale_lines)
        # Mark remaining unmatched RMAs
        not_linked_rmas = rma_to_link.filtered(lambda r: not r.move_id)
        not_linked_rmas.has_sale_auto_detect_issue = True
        not_linked_rmas.sale_auto_detect_note = _(
            "No delivery move found or insufficient delivered quantity."
        )
        return True

    def _map_rmas_to_sale_lines(self):
        rma_with_so_suggestion = self.filtered("order_id")
        rma_without_so_suggestion = self - rma_with_so_suggestion
        rma_by_sale_lines = {}
        for rma in rma_with_so_suggestion:
            sale_lines = rma.order_id.order_line.filtered(
                lambda line, r=rma: line.product_id == r.product_id
            )
            sale_lines = self._filter_sale_lines_by_delivery_move(sale_lines)
            sale_lines = self._sort_sale_lines_by_order_date(sale_lines)
            rma_by_sale_lines[rma] = sale_lines

        rma_groups = rma_without_so_suggestion._group_rmas_for_sale_auto_link()
        for (partner, product, operation), rmas in rma_groups.items():
            sale_lines = self._get_eligible_sale_lines(partner, product, operation)
            rma_by_sale_lines[rmas] = sale_lines
        return rma_by_sale_lines

    def _group_rmas_for_sale_auto_link(self):
        """return grouped rmas by (partner, product, operation)"""
        rma_groups = defaultdict(lambda: self.browse())
        for rec in self:
            if rec.state != "draft" or rec.move_id:
                continue
            return_eligibility_days = rec.operation_id.return_eligibility_days or 0
            if return_eligibility_days <= 0:
                continue
            rma_groups[(rec.partner_id, rec.product_id, rec.operation_id)] += rec
        return rma_groups

    @api.model
    def _get_eligible_sale_lines(self, partner, product, operation):
        # filter only sale line that are delivered and have qty not linked to rma
        # sort by date order
        sale_lines = self.env["sale.order.line"].search(
            self._get_eligible_sale_lines_domain(partner, product, operation),
        )
        sale_lines = self._filter_sale_lines_by_delivery_move(sale_lines)
        sale_lines = self._sort_sale_lines_by_order_date(sale_lines)
        return sale_lines

    @api.model
    def _get_eligible_sale_lines_domain(self, partner, product, operation):
        return_eligibility_days = operation.return_eligibility_days or 0
        oldest_date = fields.Date.to_date(fields.Date.today()) - timedelta(
            days=return_eligibility_days
        )
        return [
            ("order_id.partner_id", "child_of", partner.id),
            ("state", "in", ["sale", "done"]),
            ("order_id.date_order", ">=", oldest_date),
            ("product_id", "=", product.id),
        ]

    @api.model
    def _filter_sale_lines_by_delivery_move(self, sale_lines):
        """get sale line only if the move is not linked"""
        return sale_lines.filtered(
            lambda sol: any(m.state == "done" and not m.rma_ids for m in sol.move_ids)
        )

    @api.model
    def _sort_sale_lines_by_order_date(self, sale_lines):
        return sale_lines.sorted(lambda sol: (sol.order_id.date_order, sol.id))

    def _link_rma_to_sale_line(self, sale_lines):
        """match between rmas and sale lines"""
        if not sale_lines:
            return False
        sale_line_delivered_qty = self._get_sale_line_delivered_qty(sale_lines)
        rmas = self.sorted("date")
        sale_lines = sale_lines.sorted(lambda sol: (sol.order_id.date_order, sol.id))

        rma_index = 0
        sale_index = 0

        while rma_index < len(rmas) and sale_index < len(sale_lines):
            rma = rmas[rma_index]
            sale_line = sale_lines[sale_index]
            remaining_qty = sale_line_delivered_qty.get(sale_line.id, 0.0)

            if remaining_qty <= 0:
                sale_index += 1
                continue

            rma_qty = rma.product_uom_qty

            if rma_qty == remaining_qty:
                # perfect match
                rma._link_rma_to_delivery_move(sale_line)
                sale_line_delivered_qty[sale_line.id] = 0.0
                rma_index += 1
                sale_index += 1
            elif rma_qty > remaining_qty:
                # rma needs more than available on this sale line
                # we copy RMA for the matched qty
                matched_rma = rma.copy({"product_uom_qty": remaining_qty})
                # reduce qty on original RMA
                rma.product_uom_qty = rma_qty - remaining_qty
                # link the matched copy to the sale line
                matched_rma._link_rma_to_delivery_move(sale_line)
                sale_line_delivered_qty[sale_line.id] = 0.0
                sale_index += 1
            else:
                # rma quantity smaller than available delivered qty
                rma._link_rma_to_delivery_move(sale_line, qty_limit=rma_qty)
                sale_line_delivered_qty[sale_line.id] = remaining_qty - rma_qty
                rma_index += 1

    @api.model
    def _get_sale_line_delivered_qty(self, sale_lines):
        """return a dict mapping sale_line.id -> delivered quantity"""
        return {line.id: line.qty_delivered or 0.0 for line in sale_lines}

    def _link_rma_to_delivery_move(self, sale_line, qty_limit=None):
        """assign stock moves from a sale line to an rma
        qty_limit can be used to cap the total assigned quantity
        """
        self.ensure_one()
        delivery_moves = sale_line.move_ids.filtered(
            lambda m: m.state == "done"
        ).sorted(lambda m: (m.date, m.id))
        if not delivery_moves:
            return

        total_assigned = 0.0
        for i, move in enumerate(delivery_moves):
            move_qty = move.product_uom_qty
            if qty_limit and total_assigned + move_qty > qty_limit:
                move_qty = qty_limit - total_assigned
            total_assigned += move_qty
            if not move_qty or qty_limit and total_assigned > qty_limit:
                break
            values = {
                "move_id": move.id,
                "picking_id": move.picking_id.id,
                "product_uom_qty": move_qty,
                "order_id": sale_line.order_id.id,
            }
            if i == 0:
                self.write(values)
            else:
                # duplicate for each additional move
                self.copy(values)
