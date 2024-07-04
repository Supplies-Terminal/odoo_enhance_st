# -*- coding: UTF-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api
import logging
_logger = logging.getLogger(__name__)
        
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

    @api.model
    def create(self, vals):
        _logger.info("------------PurchaseOrderLine: create--------------")
        orderLine = super(PurchaseOrderLine, self).create(vals)
        return orderLine


    @api.model
    def get_current_shortage(self, product_id, warehouse_id):
        """Get current shortage for a specific product considering two-step delivery and specific warehouse"""
        # 找到所有涉及销售订单和制造订单且拣货类型为“Pick”的stock.move记录
        moves = self.env['stock.move'].search([
            ('state', 'in', ['confirmed', 'waiting', 'assigned']),
            ('product_id', '=', product_id),
            ('picking_id.picking_type_id.warehouse_id', '=', warehouse_id),
            ('picking_id.picking_type_id.name', '=', 'Pick'),
            '|',
            ('picking_id.sale_id', '!=', False),
            ('picking_id.group_id.mrp_production_ids', '!=', False),
        ])

        shortage_list = []

        for move in moves:
            demand_qty = move.product_uom_qty
            reserved_qty = move.reserved_availability
            shortage_qty = demand_qty - reserved_qty

            if shortage_qty > 0:
                shortage_list.append({
                    'move_id': move.id,
                    'product_id': move.product_id.id,
                    'product_name': move.product_id.name,
                    'demand_qty': demand_qty,
                    'reserved_qty': reserved_qty,
                    'shortage_qty': shortage_qty,
                    'origin': move.origin,
                    'picking_id': move.picking_id.id,
                    'picking_type': move.picking_id.picking_type_id.name,
                    'warehouse_id': move.picking_id.picking_type_id.warehouse_id.id,
                    'warehouse_name': move.picking_id.picking_type_id.warehouse_id.name,
                    'sale_order_id': move.picking_id.sale_id.id if move.picking_id.sale_id else False,
                    'production_order_id': move.picking_id.group_id.mrp_production_ids.id if move.picking_id.group_id.mrp_production_ids else False,
                })

        return shortage_list

    @api.model
    def create(self, vals):
        _logger.info("------------PurchaseOrderLine: create--------------")
        order_line = super(PurchaseOrderLine, self).create(vals)
        if 'replenish' in order_line.order_id.origin.lower() or '补货' in order_line.order_id.origin.lower():
            order_line._insert_shortage_sources()
        return order_line

    def write(self, vals):
        _logger.info("------------PurchaseOrderLine: write--------------")
        _logger.info(self)
        res = super(PurchaseOrderLine, self).write(vals)
        for line in self:
            if 'replenish' in line.order_id.origin.lower() or '补货' in line.order_id.origin.lower():
                line._insert_shortage_sources()
        return res
        
    def _insert_shortage_sources(self):
        _logger.info(f"------------PurchaseOrderLine: _insert_shortage_sources--------------%s", self.id)
        purchase_order_line_so_model = self.env['purchase.order.line.so']
        purchase_order_line_mo_model = self.env['purchase.order.line.mo']

        for line in self:
            _logger.info(line)
            warehouse = self.env['stock.warehouse'].search([('company_id', '=', line.order_id.company_id.id)], limit=1)
            warehouse_id = warehouse.id

            shortage_list = self._get_current_shortage(line.product_id.id, warehouse_id)
            _logger.info(shortage_list)
            
            for shortage in shortage_list:
                if shortage['sale_order_id']:
                    existing_so_line = purchase_order_line_so_model.search([
                        ('purchase_order_line_id', '=', line.id),
                        ('sale_order_id', '=', shortage['sale_order_id'])
                    ], limit=1)
                    if existing_so_line:
                        existing_so_line.quantity = shortage['shortage_qty']
                    else:
                        purchase_order_line_so_model.create({
                            'purchase_order_line_id': line.id,
                            'sale_order_id': shortage['sale_order_id'],
                            'quantity': shortage['shortage_qty'],
                        })
                if shortage['production_order_id']:
                    existing_mo_line = purchase_order_line_mo_model.search([
                        ('purchase_order_line_id', '=', line.id),
                        ('manufacturing_order_id', '=', shortage['production_order_id'])
                    ], limit=1)
                    if existing_mo_line:
                        existing_mo_line.quantity = shortage['shortage_qty']
                    else:
                        purchase_order_line_mo_model.create({
                            'purchase_order_line_id': line.id,
                            'manufacturing_order_id': shortage['production_order_id'],
                            'quantity': shortage['shortage_qty'],
                        })
    @api.model
    def _get_current_shortage(self, product_id, warehouse_id):
        _logger.info(f"------------PurchaseOrderLine: _get_current_shortage--------------%s %s", product_id, warehouse_id)
        moves = self.env['stock.move'].search([
            ('state', 'in', ['confirmed', 'waiting', 'assigned']),
            ('product_id', '=', product_id),
            ('picking_id.picking_type_id.warehouse_id', '=', warehouse_id),
            ('picking_id.picking_type_id.name', '=', 'Pick'),
            '|',
            ('picking_id.sale_id', '!=', False),
            ('picking_id.group_id.mrp_production_ids', '!=', False),
        ])

        shortage_list = []

        for move in moves:
            demand_qty = move.product_uom_qty
            reserved_qty = move.reserved_availability
            shortage_qty = demand_qty - reserved_qty

            if shortage_qty > 0:
                shortage_list.append({
                    'move_id': move.id,
                    'product_id': move.product_id.id,
                    'product_name': move.product_id.name,
                    'demand_qty': demand_qty,
                    'reserved_qty': reserved_qty,
                    'shortage_qty': shortage_qty,
                    'origin': move.origin,
                    'picking_id': move.picking_id.id,
                    'picking_type': move.picking_type_id.name,
                    'warehouse_id': move.picking_type_id.warehouse_id.id,
                    'warehouse_name': move.picking_type_id.warehouse_id.name,
                    'sale_order_id': move.picking_id.sale_id.id if move.picking_id.sale_id else False,
                    'production_order_id': move.picking_id.group_id.mrp_production_ids.id if move.picking_id.group_id.mrp_production_ids else False,
                })

        return shortage_list
