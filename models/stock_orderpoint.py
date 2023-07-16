# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from datetime import datetime, time
from odoo import SUPERUSER_ID, _, api, fields, models

_logger = logging.getLogger(__name__)

class StockWarehouseOrderpoint(models.Model):
    _inherit = "stock.warehouse.orderpoint"
    
    def action_replace(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('odoo_enhance_st.action_stock_orderpoint_replace')
        action['name'] = _('Replace %s', self.product_id.display_name)
        res = self.env['stock.orderpoint.replace'].create({
            'product_id': self.product_id.id,
        })
        action['res_id'] = res.id
        return action
