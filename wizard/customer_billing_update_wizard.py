# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging
from datetime import datetime, date
import calendar

_logger = logging.getLogger(__name__)


class CustomerBillingUpdateWizard(models.TransientModel):
    _name = 'customer.billing.update.wizard'
    _description = 'Customer Billing Update Wizard'

    company_id = fields.Many2one(
        'res.company', 
        string='Sales Company', 
        required=True,
        default=lambda self: self.env.company,
        help='Select the sales company to process'
    )
    
    partner_id = fields.Many2one(
        'res.partner', 
        string='Customer', 
        required=True,
        domain="[('is_company', '=', True)]",
        help='Select the customer to process'
    )
    
    billing_company_id = fields.Many2one(
        'res.company', 
        string='Billing Company', 
        required=True,
        help='Select the billing company'
    )
    
    billing_partner_id = fields.Many2one(
        'res.partner', 
        string='Billing Vendor', 
        required=True,
        domain="[('is_company', '=', True), ('company_id', '=', billing_company_id)]",
        help='Select the vendor in the billing company'
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
    
    update_type = fields.Selection([
        ('monthly', 'Monthly Update'),
        ('date_range', 'Date Range Update'),
        ('specific_month', 'Specific Month'),
    ], string='Update Type', default='monthly', required=True)
    
    specific_month = fields.Date(
        string='Specific Month',
        help='Select a specific month to process (e.g., 2024-01-01 for January 2024)'
    )
    
    force_recreate = fields.Boolean(
        string='Force Recreate Bills',
        default=False,
        help='If checked, will delete existing bills and recreate them'
    )
    
    dry_run = fields.Boolean(
        string='Dry Run (Preview Only)',
        default=True,
        help='If checked, will only show what would be processed without making changes'
    )
    
    result_summary = fields.Text(
        string='Processing Summary',
        readonly=True,
        help='Summary of the processing results'
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

    @api.onchange('update_type')
    def _onchange_update_type(self):
        """当更新类型改变时，更新相关字段"""
        if self.update_type == 'specific_month':
            self.start_date = False
            self.end_date = False
        elif self.update_type == 'monthly':
            self.start_date = self._get_default_start_date()
            self.end_date = self._get_default_end_date()
            self.specific_month = False

    @api.onchange('specific_month')
    def _onchange_specific_month(self):
        """当特定月份改变时，自动设置开始和结束日期"""
        if self.specific_month:
            start_date = date(self.specific_month.year, self.specific_month.month, 1)
            last_day = calendar.monthrange(self.specific_month.year, self.specific_month.month)[1]
            end_date = date(self.specific_month.year, self.specific_month.month, last_day)
            self.start_date = start_date
            self.end_date = end_date

    @api.onchange('billing_company_id')
    def _onchange_billing_company_id(self):
        """当账单公司改变时，清空并更新供应商选择域"""
        if self.billing_company_id:
            self.billing_partner_id = False
            return {
                'domain': {
                    'billing_partner_id': [
                        ('is_company', '=', True),
                        ('company_id', '=', self.billing_company_id.id)
                    ]
                }
            }
        else:
            self.billing_partner_id = False
            return {
                'domain': {
                    'billing_partner_id': [('id', '=', False)]
                }
            }

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        """检查日期范围的有效性"""
        for record in self:
            if record.start_date and record.end_date:
                if record.start_date > record.end_date:
                    raise ValidationError(_('Start date cannot be later than end date'))
                
                # 检查日期范围是否过大（超过12个月）
                from dateutil.relativedelta import relativedelta
                if record.end_date - record.start_date > relativedelta(months=12):
                    raise ValidationError(_('Date range cannot exceed 12 months'))

    def action_preview(self):
        """预览将要处理的数据"""
        self.ensure_one()
        
        # 验证映射关系
        mapping = self._get_or_create_mapping()
        if not mapping:
            return
        
        # 获取发票数据
        invoices = self._get_invoices_for_period()
        
        # 生成预览报告
        summary = self._generate_preview_summary(invoices, mapping)
        self.result_summary = summary
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'customer.billing.update.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_process(self):
        """执行实际的账单更新处理"""
        self.ensure_one()
        
        try:
            # 验证映射关系
            mapping = self._get_or_create_mapping()
            if not mapping:
                raise UserError(_('Failed to create or find billing mapping'))
            
            # 获取发票数据
            invoices = self._get_invoices_for_period()
            
            if not invoices:
                raise UserError(_('No invoices found for the specified period and criteria'))
            
            # 执行账单更新
            processed_count = self._process_billing_updates(invoices, mapping)
            
            # 生成结果报告
            summary = self._generate_result_summary(invoices, processed_count)
            self.result_summary = summary
            
            # 显示成功消息
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Successfully processed %d invoices and updated billing for the period %s to %s') % (
                        processed_count, self.start_date, self.end_date
                    ),
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            _logger.error(f"Error processing billing updates: {str(e)}")
            raise UserError(_('Error processing billing updates: %s') % str(e))

    def _get_or_create_mapping(self):
        """获取或创建客户账单映射关系"""
        mapping = self.env['customer.billing.mapping'].search([
            ('company_id', '=', self.company_id.id),
            ('partner_id', '=', self.partner_id.id),
            ('active', '=', True)
        ], limit=1)
        
        if not mapping:
            # 创建新的映射关系
            mapping = self.env['customer.billing.mapping'].create({
                'company_id': self.company_id.id,
                'partner_id': self.partner_id.id,
                'billing_company_id': self.billing_company_id.id,
                'billing_partner_id': self.billing_partner_id.id,
                'active': True,
            })
            _logger.info(f"Created new billing mapping: {mapping.id}")
        
        return mapping

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

    def _generate_preview_summary(self, invoices, mapping):
        """生成预览摘要"""
        if not invoices:
            return _('No invoices found for the specified period and criteria.')
        
        # 按日期分组统计
        date_groups = {}
        for invoice in invoices:
            date_key = invoice.invoice_date.strftime('%Y-%m-%d')
            if date_key not in date_groups:
                date_groups[date_key] = {'count': 0, 'total_amount': 0.0}
            date_groups[date_key]['count'] += 1
            date_groups[date_key]['total_amount'] += invoice.amount_total
        
        summary = f"""PREVIEW SUMMARY
================
Company: {self.company_id.name}
Customer: {self.partner_id.name}
Billing Company: {self.billing_company_id.name}
Billing Vendor: {self.billing_partner_id.name}
Period: {self.start_date} to {self.end_date}
Total Invoices: {len(invoices)}

Daily Breakdown:
"""
        
        for date_key in sorted(date_groups.keys()):
            group = date_groups[date_key]
            summary += f"{date_key}: {group['count']} invoices, ${group['total_amount']:.2f}\n"
        
        summary += f"\nThis will create/update bills for {len(date_groups)} different dates."
        
        return summary

    def _generate_result_summary(self, invoices, processed_count):
        """生成处理结果摘要"""
        summary = f"""PROCESSING COMPLETED
====================
Company: {self.company_id.name}
Customer: {self.partner_id.name}
Billing Company: {self.billing_company_id.name}
Billing Vendor: {self.billing_partner_id.name}
Period: {self.start_date} to {self.end_date}
Total Invoices Processed: {len(invoices)}
Bills Updated/Created: {processed_count}

Processing completed successfully at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return summary

    def _process_billing_updates(self, invoices, mapping):
        """执行账单更新处理"""
        processed_count = 0
        
        # 按日期分组处理
        date_groups = {}
        for invoice in invoices:
            date_key = invoice.invoice_date
            if date_key not in date_groups:
                date_groups[date_key] = []
            date_groups[date_key].append(invoice)
        
        for invoice_date, date_invoices in date_groups.items():
            _logger.info(f"Processing invoices for date: {invoice_date}")
            
            # 处理该日期的所有发票
            for invoice in date_invoices:
                try:
                    # 调用现有的更新逻辑
                    invoice._update_customer_billing()
                    processed_count += 1
                    _logger.info(f"Successfully processed invoice: {invoice.name}")
                except Exception as e:
                    _logger.error(f"Error processing invoice {invoice.name}: {str(e)}")
                    continue
        
        return processed_count
