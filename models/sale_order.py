# -*- coding: UTF-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = "sale.order"

    date_place = fields.Datetime(string='Place Date', required=True, readonly=True, index=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)]}, copy=False, default=fields.Datetime.now, help="The date customers submit the quotation")