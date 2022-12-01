# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models, tools

class Partner(models.Model):
    _inherit = "res.partner"
    _rec_name = 'full_name'
    
    website_ids = fields.Many2many('website', string='App Websites')

    full_name = fields.Char(compute='_compute_full_name', store=False)

    @api.depends('name', 'ref')
    def _compute_full_name(self):
        for rec in self:
            name = "%s" % rec.name
            if (rec.ref):
                name = "%s (%s)" % (rec.name, rec.ref)
                
            rec.full_name = name

    def name_get(self):
        res = []
        # res_partner_search_mode = self.env.context.get('res_partner_search_mode')
        for rec in self:
            name = "%s" % rec.name
            if (rec.ref):
                name = "%s (%s)" % (rec.name, rec.ref)
               
            res.append((rec.id, name))
            return res

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        recs = self.search([('full_name', operator, name)] + args, limit=limit)
        if not recs.ids:
            return super(ResPartner, self).name_search(name=name, args=args,
                                                       operator=operator,
                                                       limit=limit)
        return recs.name_get()