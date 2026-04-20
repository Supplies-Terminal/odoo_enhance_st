# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class CustomerBillingMapping(models.Model):
    _name = 'customer.billing.mapping'
    _description = 'Customer Billing Mapping'
    _rec_name = 'partner_id'

    company_id = fields.Many2one(
        'res.company', 
        string='Sales Company', 
        required=True,
        default=lambda self: self.env.company,
        help='Company that owns the sales invoice'
    )
    partner_id = fields.Many2one(
        'res.partner', 
        string='Customer', 
        required=True,
        domain="[('is_company', '=', True)]",
        help='Customer that needs billing'
    )
    billing_company_id = fields.Many2one(
        'res.company', 
        string='Billing Company', 
        required=True,
        help='Target company to generate bills'
    )
    billing_partner_id = fields.Many2one(
        'res.partner', 
        string='Billing Vendor', 
        required=True,
        domain="[('is_company', '=', True)]",
        help='Vendor partner in the billing company (e.g., "syntac" customer in jo\'s tea company)'
    )
    chart_of_account_id = fields.Many2one(
        'account.account',
        string='Chart of Account',
        required=True,
        domain="[('company_id', '=', billing_company_id), ('deprecated', '=', False)]",
        help='Expense account used when creating billing documents'
    )
    active = fields.Boolean(default=True, string='Active')
    
    _sql_constraints = [
        ('unique_mapping', 'unique(company_id, partner_id, billing_company_id)', 
         'Only one billing company can be mapped to the same customer under the same sales company!')
    ]

    @api.constrains('company_id', 'billing_company_id')
    def _check_companies_different(self):
        for record in self:
            if record.company_id == record.billing_company_id:
                raise ValidationError(_('Sales company and billing company cannot be the same company!'))

    @api.constrains('billing_partner_id', 'billing_company_id')
    def _check_billing_partner_company(self):
        for record in self:
            if record.billing_partner_id and record.billing_company_id:
                if record.billing_partner_id.company_id and record.billing_partner_id.company_id != record.billing_company_id:
                    raise ValidationError(_('Billing vendor must belong to the billing company!'))

    @api.constrains('chart_of_account_id', 'billing_company_id')
    def _check_chart_of_account_company(self):
        for record in self:
            if record.chart_of_account_id and record.billing_company_id:
                if record.chart_of_account_id.company_id != record.billing_company_id:
                    raise ValidationError(_('Chart of Account must belong to the billing company!'))

    @api.onchange('billing_company_id')
    def _onchange_billing_company_id(self):
        """当账单公司改变时，清空并更新供应商选择域"""
        if self.billing_company_id:
            # 清空供应商选择
            self.billing_partner_id = False
            self.chart_of_account_id = False
            # 返回动态域，使用 sudo() 来跨公司查询
            return {
                'domain': {
                    'billing_partner_id': [
                        ('is_company', '=', True),
                        ('company_id', '=', self.billing_company_id.id)
                    ],
                    'chart_of_account_id': [
                        ('company_id', '=', self.billing_company_id.id),
                        ('deprecated', '=', False),
                    ],
                }
            }
        else:
            # 如果没有选择账单公司，清空供应商
            self.billing_partner_id = False
            self.chart_of_account_id = False
            return {
                'domain': {
                    'billing_partner_id': [('id', '=', False)],
                    'chart_of_account_id': [('id', '=', False)],
                }
            }

    @api.onchange('billing_partner_id')
    def _onchange_billing_partner_id(self):
        """当供应商改变时，验证是否属于账单公司"""
        if self.billing_partner_id and self.billing_company_id:
            if self.billing_partner_id.company_id and self.billing_partner_id.company_id != self.billing_company_id:
                return {
                    'warning': {
                        'title': _('Warning'),
                        'message': _('Selected vendor does not belong to the billing company. Please select a vendor from the billing company.')
                    }
                }
