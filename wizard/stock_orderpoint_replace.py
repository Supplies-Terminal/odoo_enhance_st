# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, Command

import logging
_logger = logging.getLogger(__name__)

class StockOrderpointReplace(models.TransientModel):
    _name = 'stock.orderpoint.replace'
    _description = 'Replace Product for Orderpoint'

    def _default_product_id(self):
        product_id = self.env.context.get('default_product_id', 0)
        return product_id

    product_id = fields.Integer(string='Product', default=_default_product_id)
    replace_id = fileds.One2many('product.product')
    orders = fields.One2many('stock.orderpoint.replace.order', 'order_id', string='Orders', compute='_compute_orders', store=True, readonly=False)

    @api.depends('product_id')
    def _compute_orders(self):
        _logger.info("------------_compute_orders------------")
        _logger.info(self.product_id)
        orders = self.env['sale.order'].search([('order_line.product_id', '=', self.product_id)])
        _logger.info(orders)

        self.orders = []
        if orders:
            self.orders = [
                Command.create({
                    'order_id': order.id,
                    'product_id': self.product_id,
                    'qty': sum(order.order_line.filtered(lambda line: line.product_id.id == product_id).mapped('product_uom_qty')),
                    'replace_id': self.replace_id,
                })
                for order in orders
            ]
            _logger.info(self.orders)

class StockOrderpointReplaceOrder(models.TransientModel):
    _name = 'stock.orderpoint.replace.order'
    _description = 'Order purchased a product'

    order_id = fields.Many2one('sale.order', string='Order', required=True, readonly=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True, readonly=True, ondelete='cascade')
    qty = fields.Integer(string="QTY", compute="_compute_qty")
    replace_id = fields.Many2one('product.product', string='Replace With', required=True, readonly=True, ondelete='cascade')
    
    def action_replace(self):
        _logger.info("------------action_replace------------")
        _logger.info(self.order_id)
        _logger.info(self.product_id)
        _logger.info(self.qty)
        _logger.info(self.replace_id)
        return self.wizard_id._action_open_modal()

    def action_empty(self):
        _logger.info("------------action_empty------------")
        _logger.info(self.order_id)
        _logger.info(self.product_id)
        _logger.info(self.qty)
        _logger.info(self.replace_id)
        return self.wizard_id._action_open_modal()
