# -*- coding: UTF-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, models, fields, api
from odoo.exceptions import UserError, AccessError, ValidationError
from odoo.tests import Form
from odoo.tools import html2plaintext

import logging
_logger = logging.getLogger(__name__)

class Rma(models.Model):
    _inherit = "rma"

    sale_company_id = fields.Many2one('res.company', string='Sold Company')
    current_company_is_virtual = fields.Boolean(string='Current Company is Virtual', compute='_compute_current_company_is_virtual')

    @api.depends('company_id')
    def _compute_current_company_is_virtual(self):
        for order in self:
            if order.company_id:
                order.current_company_is_virtual = order.company_id.is_virtual
            else:
                order.current_company_is_virtual = False

    @api.model
    def create(self, vals):
        # Set sale_company_id based on order_id
        if 'order_id' in vals:
            sale_order = self.env['sale.order'].browse(vals['order_id'])
            if sale_order and sale_order.sale_company_id:
                vals['sale_company_id'] = sale_order.sale_company_id.id
                
        if self.current_company_is_virtual and not vals.get('sale_company_id'):
            raise UserError(_('Sales Company is required for virtual companies.'))
        return super(Rma, self).create(vals)

    def write(self, vals):
        for order in self:
            if order.current_company_is_virtual and not order.sale_company_id and not vals.get('sale_company_id'):
                raise UserError(_('Sales Company is required for virtual companies.'))
        return super(Rma, self).write(vals)

    def action_refund(self):
        """Invoked when 'Refund' button in rma form view is clicked
        and 'rma_refund_action_server' server action is run.
        """
        group_dict = {}
        for record in self.filtered("can_be_refunded"):
            key = (record.partner_invoice_id.id, record.company_id.id)
            group_dict.setdefault(key, self.env["rma"])
            group_dict[key] |= record
        for rmas in group_dict.values():
            company_id = rmas[0].sale_company_id.id if rmas[0].sale_company_id else rmas[0].company_id.id
        
            _logger.info('===')
            _logger.info(company_id)
            origin = ", ".join(rmas.mapped("name"))
            invoice_form = Form(
                self.env["account.move"]
                .sudo()
                .with_company(company_id)
                .with_context(
                    default_move_type="out_refund",
                ),
                "account.view_move_form",
            )
            rmas[0]._prepare_refund(invoice_form, origin)
            refund = invoice_form.save()
            _logger.info('===>')
            _logger.info(refund)
            _logger.info(refund.company_id)
            for rma in rmas:
                # For each iteration the Form is edited, a new invoice line
                # is added and then saved. This is to generate the other
                # lines of the accounting entry and to specify the associated
                # RMA to that new invoice line.
                invoice_form = Form(refund)
                with invoice_form.invoice_line_ids.new() as line_form:
                    rma._prepare_refund_line(line_form)
                refund = invoice_form.save()
                line = refund.invoice_line_ids.filtered(lambda r: not r.rma_id)
                line.rma_id = rma.id
                rma.write(
                    {
                        "refund_line_id": line.id,
                        "refund_id": refund.id,
                        "state": "refunded",
                    }
                )
            refund.invoice_origin = origin
            refund.with_user(self.env.uid).message_post_with_view(
                "mail.message_origin_link",
                values={"self": refund, "origin": rmas},
                subtype_id=self.env.ref("mail.mt_note").id,
            )
            # 自动确认credit note
            refund.action_post()