# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import datetime, time
from dateutil.relativedelta import relativedelta
import json
import logging
_logger = logging.getLogger(__name__)

from odoo import api, fields, models, _

class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    today_po_count = fields.Integer(
        string="Purchase Orders with Same Confirmation Date",
        compute='_compute_today_purchase_order_count',
        store=False
    )
    
    def _compute_today_purchase_order_count(self):
        for order in self:
            order.today_po_count = 0
            
            _logger.info('-_compute_today_purchase_order_count -')
            _logger.info(order.date_approve)
            if order.date_approve:
                date_approve = order.date_approve.date()
    
                start_of_day = datetime.combine(date_approve, time.min)
                end_of_day = datetime.combine(date_approve, time.max)
                domain = [('date_approve', '>=', start_of_day), ('date_approve', '<=', end_of_day), ('state', 'in', ['purchase', 'done'])]
    
                confirmation_date_purchase_order_count = self.search_count(domain)
                _logger.info(confirmation_date_purchase_order_count)
                order.today_po_count = confirmation_date_purchase_order_count