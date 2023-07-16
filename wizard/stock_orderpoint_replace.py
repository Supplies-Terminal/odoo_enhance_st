# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, Command, _

import logging
_logger = logging.getLogger(__name__)

class StockOrderpointReplace(models.TransientModel):
    _name = 'stock.orderpoint.replace'
    _description = 'Replace Product for Orderpoint'

    product_id = fields.Many2one('product.product', string='Product', required=True, readonly=True)
    replace_id = fields.Many2one('product.product', string='Replace With')
    orders = fields.One2many('stock.orderpoint.replace.order', 'order_id', string='Orders', compute='_compute_orders', store=True, readonly=False)

    @api.depends('product_id')
    def _compute_orders(self):
        _logger.info("------------_compute_orders------------")
        _logger.info(self.product_id)
        orderList = self.env['sale.order'].sudo().search(['&', ('order_line.product_id.id', '=', self.product_id.id), ('state', '=', 'sale')])
        _logger.info(orderList)
        _logger.info("------------xxxx------------")
        _logger.info(orderList[0].id)

        self.orders = []
        if orderList:
            if self.replace_id:
                for order in orderList:
                    order_line_values = {
                        'order_id': order.id,
                        'ord_id': order.id,
                        'partner_id': order.partner_id.id,
                        'product_id': self.product_id.id,
                        'qty': sum(order.order_line.filtered(lambda line: line.product_id.id == self.product_id.id).mapped('product_uom_qty')),
                    }
                    _logger.info(order_line_values)
                    self.orders = [(0, 0, order_line_values)]
            else:
                for order in orderList:
                    order_line_values = {
                        'order_id': order.id,
                        'ord_id': order.id,
                        'partner_id': order.partner_id.id,
                        'product_id': self.product_id.id,
                        'qty': sum(order.order_line.filtered(lambda line: line.product_id.id == self.product_id.id).mapped('product_uom_qty')),
                    }
                    _logger.info(order_line_values)
                    self.orders = [(0, 0, order_line_values)]
        _logger.info("------------yyy------------")
        _logger.info(self.orders)
        _logger.info(self.orders[0].order_id.id)
        _logger.info(self.orders[0].ord_id.id)
        _logger.info(self.orders[0].partner_id.id)
        _logger.info(self.orders[0].product_id.id)
        _logger.info(self.orders[0].qty)
            
    @api.onchange('replace_id')
    def _onchange_replace_id(self):
        for order in self.orders:
            order.replace_id = self.replace_id
            
class StockOrderpointReplaceOrder(models.TransientModel):
    _name = 'stock.orderpoint.replace.order'
    _description = 'Order purchased a product'

    order_id = fields.Many2one('stock.orderpoint.replace.order', string='Replace', required=True, readonly=True)
    ord_id = fields.Many2one('sale.order', string='Order', required=True, readonly=True)
    partner_id = fields.Many2one('res.partner', string='Customer', required=True, readonly=True)
    product_id = fields.Many2one('product.product', string='Product', required=True, readonly=True)
    qty = fields.Float(string="QTY")
    replace_id = fields.Many2one('product.product', string='Replace With')
    
    def action_replace(self):
        _logger.info("------------action_replace------------")
        _logger.info(self.order_id)
        _logger.info("------------1-----------")
        _logger.info(self.replace_id)
        order = self.env['sale.order'].sudo().browse(self.ord_id.id)
        _logger.info(order.order_line)
        order_lines = order.order_line.filtered(lambda line: line.product_id.id == self.product_id.id)
        order_lines.write({'product_uom_qty': 0}) # 把原来的清零
        _logger.info("------------2-----------")
        new_product_values = {
            'product_id': self.replace_id.id,
            'name': self.replace_id.display_name,
            'product_uom_qty': self.qty,
            'product_uom': self.replace_id.uom_id.id
        }
        _logger.info(new_product_values)
        # 在One2many字段中追加记录
        order.order_line = [(0, 0, new_product_values)] # 置换成为新的 （数量、计量单位等要处理）

        _logger.info("------------open_modal------------")
        action = self.env['ir.actions.actions']._for_xml_id('odoo_enhance_st.action_stock_orderpoint_replace')
        action['name'] = _('Replace %s', self.product_id.display_name)
        if self.replace_id:
            res = self.env['stock.orderpoint.replace'].create({
                'product_id': self.product_id.id,
                'replace_id': self.replace_id.id,
            })
        else:
            res = self.env['stock.orderpoint.replace'].create({
                'product_id': self.product_id.id,
            })
        action['res_id'] = res.id
        _logger.info(action['res_id'])
        return action
        
    def action_empty(self):
        _logger.info("------------action_empty------------")
        _logger.info(self.order_id)
        order = self.env['sale.order'].sudo().browse(self.ord_id.id)
        _logger.info(order.order_line)
        order_lines = order.order_line.filtered(lambda line: line.product_id.id == self.product_id.id)
        order_lines.write({'product_uom_qty': 0})

        _logger.info("------------open_modal------------")
        action = self.env['ir.actions.actions']._for_xml_id('odoo_enhance_st.action_stock_orderpoint_replace')
        action['name'] = _('Replace %s', self.product_id.display_name)
        if self.replace_id:
            res = self.env['stock.orderpoint.replace'].create({
                'product_id': self.product_id.id,
                'replace_id': self.replace_id.id,
            })
        else:
            res = self.env['stock.orderpoint.replace'].create({
                'product_id': self.product_id.id,
            })
        action['res_id'] = res.id
        _logger.info(action['res_id'])
        return action
