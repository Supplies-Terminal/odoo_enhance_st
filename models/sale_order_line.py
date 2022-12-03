import logging

from odoo import api, fields, models, _
from odoo.http import request
from odoo.osv import expression
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = "sale.order"

    price_additional = fields.Float('Unit Price', copy=False)
