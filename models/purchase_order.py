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

class ReportPurchaseOrderAllocation(models.AbstractModel):
    _name = 'report.odoo_enhance_st.report_purchase_order_allocation'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['purchase.order'].browse(docids)
        allocation_data = docs._get_allocation_data()
        return {
            'doc_ids': docids,
            'doc_model': 'purchase.order',
            'docs': allocation_data,
        }