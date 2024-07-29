# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models, tools

class Partner(models.Model):
    _inherit = "res.partner"
    _rec_name = 'full_name'
    
    website_ids = fields.Many2many('website', string='App Websites')

    full_name = fields.Char(compute='_compute_full_name', store=True)

    @api.depends('name', 'ref')
    def _compute_full_name(self):
        for rec in self:
            name = "%s" % rec.name
            if (rec.ref):
                name = "%s (%s)" % (rec.name, rec.ref)
                
            rec.full_name = name

    def name_get(self):
        recs = []
        # res_partner_search_mode = self.env.context.get('res_partner_search_mode')
        for rec in self:
            name = "%s" % rec.name
            if (rec.ref):
                name = "%s (%s)" % (rec.name, rec.ref)
               
            recs.append((rec.id, name))
        return recs

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        recs = self.search([('full_name', operator, name)] + args, limit=limit)

        if not recs.ids:
            return super(Partner, self)._name_search(name=name, args=args,
                                                       operator=operator,
                                                       limit=limit)
        return recs.name_get()


    def _get_private_contact_domain(self):
        if self.self.env.company.private_contact_only:
            return [('company_id', '!=', False), ('company_id', '=', self.env.company.id)]
        return []

class ResPartnerRule(models.Model):
    _inherit = 'ir.rule'

    def _compute_domain(self):
        domain = super(ResPartnerRule, self)._compute_domain()
        if self.model_id.model == 'res.partner':
            domain += self.env['res.partner']._get_private_contact_domain()
        return domain