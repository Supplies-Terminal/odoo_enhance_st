# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import datetime, time
from dateutil.relativedelta import relativedelta
from functools import partial
from itertools import groupby
import json

from markupsafe import escape, Markup
from pytz import timezone, UTC
from werkzeug.urls import url_encode

from odoo import api, fields, models, _
from odoo.osv import expression
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.misc import formatLang, get_lang, format_amount


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