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

