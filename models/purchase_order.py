# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import datetime, time
from dateutil.relativedelta import relativedelta
import json

from odoo import api, fields, models, _

class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    today_po_count = fields.Integer(
        string="Today's Purchase Orders",
        compute='_compute_today_purchase_order_count'
    )
    
    def _compute_today_purchase_order_count(self):
        today = datetime.now().date()
        domain = [('create_date', '>=', today), ('state', 'in', ['purchase', 'done'])]
        today_purchase_order_count = self.search_count(domain)
        self.today_po_count = today_purchase_order_count