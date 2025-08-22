# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
from datetime import date
import calendar

_logger = logging.getLogger(__name__)


class CustomerBillingUpdateWizard(models.TransientModel):
    """
    客户账单更新向导
    
    使用统一的事件驱动逻辑处理发票：
    - 草稿状态：使用 _handle_invoice_state_change() 方法
    - 已过账状态：使用 _handle_invoice_state_change() 方法
    
    这样可以避免重复触发，提高处理效率。
    """
    _name = 'customer.billing.update.wizard'
    _description = 'Customer Billing Update Wizard'

    company_id = fields.Many2one(
        'res.company', 
        string='Company', 
        required=True,
        default=lambda self: self.env.company,
        help='Select the company to process'
    )
    
    partner_id = fields.Many2one(
        'res.partner', 
        string='Customer', 
        required=True,
        domain="[('is_company', '=', True)]",
        help='Select the customer to process'
    )
    
    start_date = fields.Date(
        string='Start Date', 
        required=True,
        default=lambda self: self._get_default_start_date(),
        help='Start date for the period to process'
    )
    
    end_date = fields.Date(
        string='End Date', 
        required=True,
        default=lambda self: self._get_default_end_date(),
        help='End date for the period to process'
    )

    @api.model
    def _get_default_start_date(self):
        """获取默认开始日期（当前月份第一天）"""
        today = date.today()
        return date(today.year, today.month, 1)

    @api.model
    def _get_default_end_date(self):
        """获取默认结束日期（当前月份最后一天）"""
        today = date.today()
        last_day = calendar.monthrange(today.year, today.month)[1]
        return date(today.year, today.month, last_day)

    def action_process(self):
        """
        执行账单更新处理
        
        使用统一的事件驱动逻辑：
        1. 草稿发票：调用 _handle_invoice_state_change()
        2. 已过账发票：调用 _handle_invoice_state_change()
        3. 草稿贷项通知单：调用 _handle_invoice_state_change()
        4. 已过账贷项通知单：调用 _handle_invoice_state_change()
        5. 其他状态：跳过处理
        
        这样可以避免重复触发，提高处理效率。
        """
        self.ensure_one()
        
        try:
            # 获取指定期间内的发票和贷项通知单
            documents = self._get_invoices_for_period()
            
            if not documents:
                raise UserError(_('No invoices or credit notes found for the specified period and criteria'))
            
            # 使用新的事件驱动逻辑处理发票和贷项通知单
            processed_count = 0
            for document in documents:
                try:
                    # 统一处理发票状态变化
                    document._handle_invoice_state_change()
                    _logger.info(f"Successfully processed {document.move_type}: {document.name} (State: {document.state})")
                    
                    processed_count += 1
                except Exception as e:
                    _logger.error(f"Error processing {document.move_type} {document.name}: {str(e)}")
                    continue
            
            # 显示成功消息
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Successfully processed %d documents (invoices and credit notes) for the period %s to %s') % (
                        processed_count, self.start_date, self.end_date
                    ),
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            _logger.error(f"Error processing billing updates: {str(e)}")
            raise UserError(_('Error processing billing updates: %s') % str(e))

    def _get_invoices_for_period(self):
        """
        获取指定期间内的发票和贷项通知单
        
        只获取草稿和已过账状态的发票和贷项通知单，因为只有这两种状态需要处理。
        """
        domain = [
            ('company_id', '=', self.company_id.id),
            ('partner_id', '=', self.partner_id.id),
            ('move_type', 'in', ['out_invoice', 'out_refund']),  # 包含销售发票和贷项通知单
            ('invoice_date', '>=', self.start_date),
            ('invoice_date', '<=', self.end_date),
            ('state', 'in', ['draft', 'posted']),  # 只处理草稿和已过账状态
        ]
        
        documents = self.env['account.move'].search(domain, order='invoice_date')
        
        # 按类型和状态分组统计
        sales_invoices = documents.filtered(lambda doc: doc.move_type == 'out_invoice')
        credit_notes = documents.filtered(lambda doc: doc.move_type == 'out_refund')
        
        draft_sales = len(sales_invoices.filtered(lambda inv: inv.state == 'draft'))
        posted_sales = len(sales_invoices.filtered(lambda inv: inv.state == 'posted'))
        draft_credits = len(credit_notes.filtered(lambda inv: inv.state == 'draft'))
        posted_credits = len(credit_notes.filtered(lambda inv: inv.state == 'posted'))
        
        _logger.info(f"Found {len(documents)} documents for period {self.start_date} to {self.end_date}")
        _logger.info(f"  - Sales invoices: {len(sales_invoices)} (Draft: {draft_sales}, Posted: {posted_sales})")
        _logger.info(f"  - Credit notes: {len(credit_notes)} (Draft: {draft_credits}, Posted: {posted_credits})")
        
        return documents
