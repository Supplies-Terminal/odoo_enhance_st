# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'

    private_product_only = fields.Boolean(string='Private Products Only', default=False)

    ricai_location_id = fields.Many2one('stock.location', string='日采发货区', domain=[('usage', '=', 'internal')])
    mrp_location_id = fields.Many2one('stock.location', string='生产物料区', domain=[('usage', '=', 'internal')])