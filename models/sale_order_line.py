# -*- coding: UTF-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api
import logging
_logger = logging.getLogger(__name__)

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    secondary_qty = fields.Float("Secondary QTY", digits='Product Unit of Measure')
    secondary_uom_id = fields.Many2one("uom.uom", 'Secondary UoM', compute='_compute_secondary_uom_id', store=True)
    secondary_uom_name = fields.Char("Secondary Unit", compute='_compute_secondary_uom_name', store=True)
    secondary_uom_enabled = fields.Boolean("Secondary UoM Enabled", compute='_compute_secondary_uom_enabled', store=True)
    secondary_uom_rate = fields.Float( "Secondary Unit Rate", compute='_compute_secondary_uom_rate', store=True)
    secondary_uom_desc = fields.Char(string='Secondary Unit Desc', compute='_compute_secondary_uom_desc', store=True)
    description_with_counts = fields.Char(string='Item Description', compute='_compute_description_with_counts', store=True)

    latest_cost = fields.Char(string='Latest Cost', compute='_compute_latest_cost', store=False)
    latest_price = fields.Char(string='Latest Price', compute='_compute_latest_price', store=True)

    @api.depends('product_id')
    def _compute_latest_cost(self):
        for rec in self:
            rec.latest_cost = '-'
            create_date = self.order_id.place_date.date()
            _logger.info("------------_compute_latest_cost------------")
            _logger.info(create_date)
            
            PurchaseOrderLineSudo = self.env['purchase.order.line'].sudo();
            pol = PurchaseOrderLineSudo.search([('product_id', '=', rec.product_id.id), ('order_id.state', 'in', ['purchase', 'done']), ('create_date', '<=', create_date + timedelta(days=1))], limit=1, order='create_date desc')
            if pol:
                rec.latest_cost = "${}/{}".format(pol.price_unit, pol.product_uom.name)  

    @api.depends('product_id')
    def _compute_latest_price(self):
        for rec in self:
            rec.latest_price = '-'
            # 获取本人之前最后购买该商品的记录
            create_date = self.order_id.place_date.date()
            _logger.info("------------_compute_latest_price------------")
            _logger.info(self.order_id.id)
            _logger.info(self.order_id.partner_id)
            _logger.info(create_date)

            if self.order_id.partner_id:
                last_order = self.env['sale.order'].sudo().search(['&', ('partner_id', '=', self.order_id.partner_id.id), 'id', '=', self.order_id.id), ('state', '=', 'sale'), ('create_date', '<=', create_date + timedelta(days=1)), ('order_line.product_id.id', '=', self.product_id.id)], order='place_date desc', limit=1)
                if last_order:
                    order_lines = last_order.order_line.filtered(lambda line: line.product_id.id == self.product_id.id)
                    if order_lines:
                        rec.latest_price = "${}/{}".format(order_lines[0].price_unit, order_lines[0].product_uom.name)  

    @api.depends('product_id')
    def _compute_secondary_uom_id(self):
        for rec in self:
            if rec.product_id.secondary_uom_enabled and rec.product_id.secondary_uom_id:
                rec.secondary_uom_id = rec.product_id.secondary_uom_id
            # else:
            #     rec.secondary_uom_id = 

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
                rec.secondary_uom_desc = "%s (%s %s)" % (rec.secondary_uom_name, rec.secondary_uom_rate, rec.product_uom.name)
            else:
                rec.secondary_uom_desc = ""

    @api.depends('secondary_uom_enabled', 'secondary_qty')
    def _compute_description_with_counts(self):
        for rec in self:
            if rec.secondary_uom_enabled:
                rec.description_with_counts = "%s (%s %s)" % (rec.name, rec.secondary_qty, rec.secondary_uom_name)
            else:
                rec.description_with_counts = rec.name

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
