# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models, tools

class Partner(models.Model):
    _inherit = "res.partner"

    website_ids = fields.Many2many('website', string='App Websites')
    approved_user = fields.Boolean("Approved")
    first_approval_status = fields.Boolean("First Approval status")

    def name_get(self):
        res = []
        res_partner_search_mode = self.env.context.get('res_partner_search_mode')
        for rec in self:
            if (rec.ref and res_partner_search_mode in ['customer', 'supplier']):
                res.append((rec.id, "%s (%s)" % (rec.name, rec.ref)))
                return res
            else:
                res.append((rec.id, "%s" % rec.name))
                return res

    # Approve user
    def action_approve_user(self):
        for partner in self:
            partner.approved_user = True
            partner.first_approval_status = True
            partner.block_user = False
            template = self.env.ref('res.partner.mail_template_user_account_approval',
                                       raise_if_not_found=False)
            if template:
                template.sudo().send_mail(partner.id, force_send=True)

    # Reject the user
    def action_reject_user(self):
        for partner in self:
            partner.approved_user = False
            partner.block_user = True
            template = self.env.ref('res.partner.mail_template_user_account_reject',
                                       raise_if_not_found=False)
            if template:
                template.sudo().send_mail(partner.id, force_send=True)
