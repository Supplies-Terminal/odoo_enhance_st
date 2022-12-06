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
    
    secondary_uom_name = fields.Char(
        "Counting Unit", compute='_compute_secondary_uom_name', store=False
    )
    secondary_uom_enabled = fields.Boolean(
        "Counting Unit Active", compute='_compute_secondary_uom_enabled', store=False
    )
    secondary_uom_rate = fields.Float(
        "Counting Unit Rate", compute='_compute_secondary_uom_rate', store=False
    )
    
    secondary_uom_desc = fields.Char(string='Counting UOM', compute='_compute_secondary_uom_desc', store=False)

    @api.depends('product_id')
    def _compute_secondary_uom_name(self):
        for rec in self:
            if rec.product_id.secondary_uom_enabled:
                rec.secondary_uom_name = rec.product_id.secondary_uom_name
            else:
                rec.secondary_uom_name = ""

    @api.depends('product_id')
    def _compute_secondary_uom_rate(self):
        for rec in self:
            if rec.product_id.secondary_uom_enabled:
                rec.secondary_uom_rate = rec.product_id.secondary_uom_rate
            else:
                rec.secondary_uom_rate = 0.00

    @api.depends('product_id')
    def _compute_secondary_uom_enabled(self):
        for rec in self:
            rec.secondary_uom_enabled = rec.product_id.secondary_uom_enabled

                
    @api.depends('secondary_uom_enabled', 'product_uom', 'secondary_uom_id', 'secondary_uom_rate')
    def _compute_secondary_uom_desc(self):
        for rec in self:
            if rec.secondary_uom_enabled:
                rec.secondary_uom_desc = "%s(%s%s)" % (rec.secondary_uom_name, rec.secondary_uom_rate, rec.product_uom.name)
            else:
                rec.secondary_uom_desc = ""

    @api.onchange('secondary_qty')
    def onchange_secondary_qty(self):
        if self and self.secondary_uom_enabled and self.product_uom:
            if self.product_uom_qty:
                self.product_uom_qty = self.secondary_qty * self.product_id.secondary_uom_rate
            else:
                self.product_uom_qty = 0

    @api.onchange('product_id')
    def onchange_secondary_uom(self):
        if self:
            for rec in self:
                if rec.product_id:
                    if rec.product_id.secondary_uom_enabled and rec.product_id.secondary_uom_id:
                        rec.secondary_uom_id = rec.product_id.secondary_uom_id.id
                        rec.product_uom_qty = rec.secondary_qty * rec.product_id.secondary_uom_rate
                    else:
                        rec.secondary_qty = 0.0
                        rec.product_uom_qty = 0.0
                else:
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
