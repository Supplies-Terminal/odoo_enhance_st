# -*- coding: UTF-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    secondary_qty = fields.Float(
        "Counting Qty",
        digits='Product Unit of Measure'
    )
    secondary_uom_id = fields.Many2one("uom.uom", 'Counting UOM')
    secondary_uom_enabled = fields.Boolean(
        "Related Counting Unit",
        related="product_id.secondary_uom_enabled"
    )

    @api.onchange('secondary_qty', 'secondary_uom_id')
    def onchange_secondary_qty(self):
        if self and self.secondary_uom_enabled and self.product_uom:
            if not self.product_uom_qty:
                self.product_uom_qty = self.secondary_qty * self.product_id.secondary_uom_rate

    @api.onchange('product_id')
    def onchange_secondary_uom(self):
        if self:
            for rec in self:
                if rec.product_id and rec.product_id.secondary_uom_enabled and rec.product_id.uom_id:
                    rec.secondary_uom_id = rec.product_id.secondary_uom_id.id
                    rec.product_uom_qty = rec.secondary_qty * rec.product_id.secondary_uom_rate
                elif not rec.product_id.sh_is_secondary_unit:
                    rec.secondary_uom_id = False
                    rec.secondary_qty = 0.0
                    rec.product_uom_qty = 0.0

    def _prepare_invoice_line(self, **optional_values):
        res = super(SaleOrderLine, self)._prepare_invoice_line(
            **optional_values
        )
        res.update({
            'secondary_qty': self.secondary_qty,
            'secondary_uom_id': self.secondary_uom_id.id,
            })
        return res
