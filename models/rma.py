# -*- coding: UTF-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, models, fields, api
from odoo.exceptions import UserError, ValidationError
import logging
_logger = logging.getLogger(__name__)

class Rma(models.Model):
    _inherit = "rma"

    sale_company_id = fields.Many2one('res.company', string='Sold Company')
    current_company_is_virtual = fields.Boolean(string='Current Company is Virtual', compute='_compute_current_company_is_virtual')

    @api.depends('company_id')
    def _compute_current_company_is_virtual(self):
        for order in self:
            _logger.info("_compute_current_company_is_virtual")
            _logger.info(order.company_id)
            if order.company_id:
                order.current_company_is_virtual = order.company_id.is_virtual
            else:
                order.current_company_is_virtual = False

    @api.model
    def create(self, vals):
        if self.current_company_is_virtual and not vals.get('sale_company_id'):
            raise UserError(_('Sales Company is required for virtual companies.'))
        return super(Rma, self).create(vals)    

    def write(self, vals):
        for order in self:
            if order.current_company_is_virtual and not order.sale_company_id and not vals.get('sale_company_id'):
                raise UserError(_('Sales Company is required for virtual companies.'))
        return super(Rma, self).write(vals)
