# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models, tools

class Partner(models.Model):
    _inherit = "res.partner"

    is_app_supplier = fields.Boolean(default=False, string='Is Supplier for App?');
    
    @api.model
    def name_get(self):
        res = []
        res_partner_search_mode = self.env.context.get('res_partner_search_mode')
        for rec in self:
            if (rec.ref and res_partner_search_mode in ['customer', 'supplier']):
                res.append((rec.id, "%s (%s)" % (rec.name, rec.ref)))
            else:
                res.append((rec.id, "%s" % rec.name))
        return res
