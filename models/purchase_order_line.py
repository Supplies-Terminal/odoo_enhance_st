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
            pol = PurchaseOrderLineSudo.search([('product_id', '=', rec.product_id.id), ('order_id.company_id', '=', rec.order_id.company_id.id), ('order_id.partner_id', '=', rec.order_id.partner_id.id), ('order_id.state', 'in', ['purchase', 'done'])], limit=1, order='id desc')
            if pol:
                rec.latest_cost = "${}/{}".format(pol.price_unit, pol.product_uom.name)  

    so_ids = fields.One2many('purchase.order.line.so', 'purchase_order_line_id', string='Sale Order Lines')
    mo_ids = fields.One2many('purchase.order.line.mo', 'purchase_order_line_id', string='Manufacturing Order Lines')

class PurchaseOrderLineSO(models.Model):
    _name = 'purchase.order.line.so'
    _description = 'Purchase Forecast Sale Order Line'

    purchase_order_line_id = fields.Many2one('purchase.order.line', string='Purchase Order Line')
    sale_order_id = fields.Many2one('sale.order', string='Sale Order')
    quantity = fields.Float(string='Quantity')

class PurchaseOrderLineMO(models.Model):
    _name = 'purchase.order.line.mo'
    _description = 'Purchase Forecast Manufacturing Order Line'

    purchase_order_line_id = fields.Many2one('purchase.order.line', string='Purchase Order Line')
    manufacturing_order_id = fields.Many2one('mrp.production', string='Manufacturing Order')
    quantity = fields.Float(string='Quantity')