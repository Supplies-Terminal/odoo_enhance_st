# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models, tools
import logging
_logger = logging.getLogger(__name__)

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
        _logger.info("-----res.partner name_search---------")
        args = args or []
        current_company = self.env.company
        
        # 根据公司设置调整搜索条件
        if current_company.private_contact_only:
            args.append(('company_id', '=', current_company.id))
        _logger.info("--------------")
        _logger.info(args)
        
        recs = self.search([('full_name', operator, name)] + args, limit=limit)

        if not recs.ids:
            return super(Partner, self)._name_search(name=name, args=args,
                                                       operator=operator,
                                                       limit=limit)
        return recs.name_get()

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        domain = domain or []
        current_company = self.env.company

        # 检查当前公司是否设置了只看私有产品
        if current_company.private_contact_only:
            domain += [('company_id', '=', current_company.id)]

        return super(Partner, self).search_read(domain=domain, fields=fields, offset=offset, limit=limit, order=order)