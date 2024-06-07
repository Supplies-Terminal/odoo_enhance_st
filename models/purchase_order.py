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

    def _get_allocation_data(self):
        allocation_data = []
        for line in self.order_line:
            for so in line.so_ids:
                allocation_data.append({
                    'source': 'SO',
                    'product': line.product_id.display_name,
                    'order': so.sale_order_id.name,
                    'quantity': so.quantity,
                    'unit': line.product_uom.name,
                })
            for mo in line.mo_ids:
                allocation_data.append({
                    'source': 'MO',
                    'product': line.product_id.display_name,
                    'order': mo.manufacturing_order_id.name,
                    'quantity': mo.quantity,
                    'unit': line.product_uom.name,
                })
        return allocation_data

    def print_allocation_report(self):
        return self.env.ref('odoo_enhance_st.action_report_purchase_order_allocation').report_action(self)


    def button_confirm(self):
        # 如果是replenishment采购单
        if self.picking_type_id.code == 'incoming' and ('replenishment' in self.origin.lower() or '补货' in self.origin.lower()):
            if not self.company_id.ricai_location_id or not self.company_id.mrp_location_id:
                raise UserError(f"Missing location...")
            _logger.info('拆分收货单')
            self._seperate_receiving_pickings()
            
        res = super(PurchaseOrder, self).button_confirm()
        return res

    def _seperate_receiving_pickings(self):
        for order in self:
            so_moves = []
            mo_moves = []
            stock_moves = []

            for line in order.order_line:
                product = line.product_id
                remaining_qty = line.product_qty

                # 分配给销售订单
                so_total = 0;
                for so in line.so_ids:
                    if remaining_qty > 0:
                        line_qty = min(remaining_qty, so.quantity)
                        remaining_qty -= line_qty
                        so_total += line_qty
                        

                # 分配给制造订单
                mo_total = 0;
                for mo in line.mo_ids:
                    if remaining_qty > 0:
                        line_qty = min(remaining_qty, mo.quantity)
                        remaining_qty -= line_qty
                        mo_total += line_qty

                if so_total > 0:
                    so_moves.append((product, so_total))

                if mo_total > 0:
                    mo_moves.append((product, mo_total))

                if remaining_qty > 0:
                    stock_moves.append((product, remaining_qty, ))
            _logger.info('so_moves')
            _logger.info(so_moves)
            _logger.info('mo_moves')
            _logger.info(mo_moves)
            _logger.info('stock_moves')
            _logger.info(stock_moves)
            if so_moves:
                self._create_seperated_picking(order, so_moves, _('Ricai Transfer'), order.company_id.ricai_location_id.id)
            if mo_moves:
                self._create_seperated_picking(order, mo_moves, _('MRP Transfer'), order.company_id.mrp_location_id.id)
            if stock_moves:
                self._create_seperated_picking(order, stock_moves, _('Stock Transfer'), order.picking_type_id.default_location_dest_id.id)

    def _create_seperated_picking(self, order, moves, origin, dest_location_id):
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'incoming'),
            ('warehouse_id.company_id', '=', order.company_id.id)
        ], limit=1)

        move_lines = [(0, 0, {
            'product_id': product.id,
            'product_uom_qty': qty,
            'product_uom': product.uom_id.id,
            'location_id': order.partner_id.property_stock_supplier.id,
            'location_dest_id': dest_location_id,
            'name': product.display_name,
        }) for product, qty in moves]

        picking = self.env['stock.picking'].create({
            'location_id': order.partner_id.property_stock_supplier.id,
            'location_dest_id': dest_location_id,
            'picking_type_id': picking_type.id,
            'origin': origin,
            'move_lines': move_lines,
            'partner_id': order.partner_id,
        })
        _logger.info(origin)
        _logger.info(picking)
        picking.action_confirm()
        picking.action_assign()
        return picking
        
class ReportPurchaseOrderAllocation(models.AbstractModel):
    _name = 'report.odoo_enhance_st.report_purchase_order_allocation'

    @api.model
    def _get_report_values(self, docids, data=None):
        _logger.info("---------_get_report_values----------")
        docs = self.env['purchase.order'].browse(docids)
        allocation_data = []
        for doc in docs:
            allocation_data.extend(doc._get_allocation_data())
        _logger.info(allocation_data)
        current_company = self.env.company
        return {
            'doc_ids': docids,
            'doc_model': 'purchase.order',
            'docs': docs,  # 传递 purchase.order 记录集
            'allocation_data': allocation_data,  # 传递 allocation_data
            'company': current_company,
        }