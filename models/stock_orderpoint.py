# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from collections import defaultdict
from datetime import datetime, time
from dateutil import relativedelta
from itertools import groupby
from psycopg2 import OperationalError

from odoo import SUPERUSER_ID, _, api, fields, models, registry
from odoo.addons.stock.models.stock_rule import ProcurementException
from odoo.exceptions import RedirectWarning, UserError, ValidationError
from odoo.osv import expression
from odoo.tools import add, float_compare, frozendict, split_every

_logger = logging.getLogger(__name__)


class StockWarehouseOrderpoint(models.Model):
    _inherit = "stock.warehouse.orderpoint"
    
    def action_replace(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('odoo_enhance_st.action_stock_orderpoint_replace')
        action['name'] = _('Replace %s', self.product_id.display_name)
        res = self.env['stock.orderpoint.replace'].create({
            'product_id': self.product_id,
        })
        action['res_id'] = res.id
        return action
