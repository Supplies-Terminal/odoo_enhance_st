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
    
    使用新的事件驱动逻辑处理发票：
    - 草稿状态：使用 _handle_draft_invoices_update() 方法
    - 已过账状态：使用 _handle_posted_invoices_update() 方法
    
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
        
        使用新的事件驱动逻辑：
        1. 草稿发票：调用 _handle_draft_invoices_update()
        2. 已过账发票：调用 _handle_posted_invoices_update()
        3. 其他状态：跳过处理
        
        这样可以避免重复触发，提高处理效率。
        """
        self.ensure_one()
        
        try:
            # 获取指定期间内的发票
            invoices = self._get_invoices_for_period()
            
            if not invoices:
                raise UserError(_('No invoices found for the specified period and criteria'))
            
            # 使用新的事件驱动逻辑处理发票
            processed_count = 0
            for invoice in invoices:
                try:
                    # 根据发票状态使用相应的事件处理方法
                    if invoice.state == 'draft':
                        # 草稿状态：使用草稿事件处理
                        invoice._handle_draft_invoices_update()
                        _logger.info(f"Successfully processed draft invoice: {invoice.name}")
                    elif invoice.state == 'posted':
                        # 已过账状态：使用过账事件处理
                        invoice._handle_posted_invoices_update()
                        _logger.info(f"Successfully processed posted invoice: {invoice.name}")
                    else:
                        # 其他状态：跳过
                        _logger.info(f"Skipping invoice {invoice.name} with state: {invoice.state}")
                        continue
                    
                    processed_count += 1
                except Exception as e:
                    _logger.error(f"Error processing invoice {invoice.name}: {str(e)}")
                    continue
            
            # 显示成功消息
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Successfully processed %d invoices for the period %s to %s') % (
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
        获取指定期间内的发票
        
        只获取草稿和已过账状态的发票，因为只有这两种状态需要处理。
        """
        domain = [
            ('company_id', '=', self.company_id.id),
            ('partner_id', '=', self.partner_id.id),
            ('move_type', '=', 'out_invoice'),
            ('invoice_date', '>=', self.start_date),
            ('invoice_date', '<=', self.end_date),
            ('state', 'in', ['draft', 'posted']),  # 只处理草稿和已过账状态
        ]
        
        invoices = self.env['account.move'].search(domain, order='invoice_date')
        
        # 按状态分组统计
        draft_count = len(invoices.filtered(lambda inv: inv.state == 'draft'))
        posted_count = len(invoices.filtered(lambda inv: inv.state == 'posted'))
        
        _logger.info(f"Found {len(invoices)} invoices for period {self.start_date} to {self.end_date}")
        _logger.info(f"  - Draft invoices: {draft_count}")
        _logger.info(f"  - Posted invoices: {posted_count}")
        
        return invoices
