# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import datetime, time
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta
import json
import logging
_logger = logging.getLogger(__name__)

from odoo import api, fields, models, _

class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    today_po_count = fields.Integer(
        string="Purchase Orders with Same Confirmation Date",
        compute='_compute_today_purchase_order_count',
        store=False
    )
    
    def _compute_today_purchase_order_count(self):
        for order in self:
            order.today_po_count = 0
            
            _logger.info('-_compute_today_purchase_order_count -')
            _logger.info(order.date_approve)
            if order.date_approve:
                date_approve = order.date_approve.date()
    
                start_of_day = datetime.combine(date_approve, time.min)
                end_of_day = datetime.combine(date_approve, time.max)
                domain = [('date_approve', '>=', start_of_day), ('date_approve', '<=', end_of_day), ('state', 'in', ['purchase', 'done'])]
    
                confirmation_date_purchase_order_count = self.search_count(domain)
                _logger.info(confirmation_date_purchase_order_count)
                order.today_po_count = confirmation_date_purchase_order_count

    def send_internal_button_action(self):
        _logger.info('-send_internal_button_action -')

        self.ensure_one()  # 确保这个方法只在单一记录集上调用
        
        if self.state != 'purchase':
            raise UserError('Order must be confirmed to perform this action.')

        # 确定销售订单应该属于哪个公司
        internal_company = self.env['res.company'].search([('partner_id', '=', self.partner_id.id)], limit=1)
        if not internal_company:
            raise UserError('Vendor is not an internal company.')

        so = self.env['sale.order'].search([('company_id', '=', internal_company.id), ('source_po_id', '=', self.id)], limit=1)
        if so:
            raise UserError('This PO is already sent to the vendor.')

        # 创建销售订单
        sale_order_vals = {
            'partner_id': self.company_id.partner_id.id,
            'company_id': internal_company.id,
            # 以下是其他可能需要设置的字段
            'origin': self.name,  # 需要将原始采购订单设置为来源
            'source_po_id': self.id # 并记录原始采购订单ID，以满足inter-company pricing
        }
        
        # 添加订单行
        order_lines = []
        for line in self.order_line:
            order_lines.append((0, 0, {
                'product_id': line.product_id.id,
                'product_uom_qty': line.product_qty,
                'price_unit': line.price_unit,
                # 您可能还需要设置其他必要的字段
            }))
        
        sale_order_vals['order_line'] = order_lines
        sale_order = self.env['sale.order'].create(sale_order_vals)
        
        # 根据需要进行其他操作，比如确认销售订单
        # sale_order.action_confirm()

        message = _('Sale order created successfully! Order #%s', sale_order.name)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': message,
                'sticky': False,  # 消息不会一直停留在屏幕上
            }
        }
        return True
    
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
        order = super(PurchaseOrder, self).create(vals)
        _logger.info(order)
        self._insert_shortage_sources(order)
        return order

    def _insert_shortage_sources(self, order):
        purchase_order_line_so_model = self.env['purchase.order.line.so']
        purchase_order_line_mo_model = self.env['purchase.order.line.mo']

        for line in order.order_line:
            _logger.info(line.product_id)
            
            product_id = line.product_id.id
            warehouse_id = self.env['stock.warehouse'].search([('company_id', '=', order.company_id.id)], limit=1).id
            _logger.info(line.warehouse_id)

            shortage_list = self.get_current_shortage(product_id, warehouse_id)
            
            _logger.info(shortage_list)
            for shortage in shortage_list:
                if shortage['sale_order_id']:
                    purchase_order_line_so_model.create({
                        'purchase_order_line_id': line.id,
                        'sale_order_id': shortage['sale_order_id'],
                        'quantity': shortage['shortage_qty'],
                    })
                if shortage['production_order_id']:
                    purchase_order_line_mo_model.create({
                        'purchase_order_line_id': line.id,
                        'manufacturing_order_id': shortage['production_order_id'],
                        'quantity': shortage['shortage_qty'],
                    })