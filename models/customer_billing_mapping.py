# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class CustomerBillingMapping(models.Model):
    _name = 'customer.billing.mapping'
    _description = '客户账单映射关系'
    _rec_name = 'partner_id'

    company_id = fields.Many2one(
        'res.company', 
        string='销售公司', 
        required=True,
        default=lambda self: self.env.company,
        help='销售发票所属的公司'
    )
    partner_id = fields.Many2one(
        'res.partner', 
        string='客户', 
        required=True,
        domain="[('is_company', '=', True)]",
        help='需要生成账单的客户'
    )
    billing_company_id = fields.Many2one(
        'res.company', 
        string='账单公司', 
        required=True,
        help='生成账单的目标公司'
    )
    active = fields.Boolean(default=True, string='启用')
    
    _sql_constraints = [
        ('unique_mapping', 'unique(company_id, partner_id, billing_company_id)', 
         '同一销售公司下的同一客户只能对应一个账单公司！')
    ]

    @api.constrains('company_id', 'billing_company_id')
    def _check_companies_different(self):
        for record in self:
            if record.company_id == record.billing_company_id:
                raise ValidationError(_('销售公司和账单公司不能是同一家公司！'))

