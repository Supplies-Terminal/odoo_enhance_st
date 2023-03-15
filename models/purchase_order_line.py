# -*- coding: UTF-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api

class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    latest_cost = fields.Char(string='Latest Cost', compute='_compute_latest_cost', store=True)

    @api.depends('product_id')
    def _compute_latest_cost(self):
        for rec in self:
            rec.latest_cost = '-'
            PurchaseOrderLineSudo = self.env['purchase.order.line'].sudo();
            pol = PurchaseOrderLineSudo.search([('product_id', '=', rec.product_id), ('order_id.state', 'in', ['purchase', 'done'])],limit=1, order='id desc')

            if pol:
                rec.latest_cost = "${}/{}".format(pol.price_unit, pol.product_uom.name)  
