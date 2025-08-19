# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
from datetime import date
import calendar

_logger = logging.getLogger(__name__)


class CustomerBillingUpdateWizard(models.TransientModel):
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
        """执行账单更新处理"""
        self.ensure_one()
        
        try:
            # 获取指定期间内的发票
            invoices = self._get_invoices_for_period()
            
            if not invoices:
                raise UserError(_('No invoices found for the specified period and criteria'))
            
            # 逐一执行_update_customer_billing
            processed_count = 0
            for invoice in invoices:
                try:
                    invoice._update_customer_billing()
                    processed_count += 1
                    _logger.info(f"Successfully processed invoice: {invoice.name}")
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
        """获取指定期间内的发票"""
        domain = [
            ('company_id', '=', self.company_id.id),
            ('partner_id', '=', self.partner_id.id),
            ('move_type', '=', 'out_invoice'),
            ('invoice_date', '>=', self.start_date),
            ('invoice_date', '<=', self.end_date),
        ]
        
        invoices = self.env['account.move'].search(domain, order='invoice_date')
        _logger.info(f"Found {len(invoices)} invoices for period {self.start_date} to {self.end_date}")
        
        return invoices
