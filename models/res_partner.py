# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models, tools

class Partner(models.Model):
    _inherit = "res.partner"

    website_ids = fields.Many2many('website', string='App Websites')

    def name_get(self):
        res = []
        # res_partner_search_mode = self.env.context.get('res_partner_search_mode')
        for rec in self:
            name = "%s" % rec.name
            if (rec.ref):
                name += ' (%s)" % rec.ref
            res.append((rec.id, name))
            return res
