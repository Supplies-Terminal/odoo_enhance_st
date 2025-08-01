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
    
    # 添加计算字段来标识客户是否属于当前公司
    is_my_customer = fields.Boolean(
        string='Is My Customer',
        compute='_compute_is_my_customer',
        search='_search_is_my_customer',
        help='标识该客户是否属于当前公司的客户（基于发票记录）'
    )

    @api.depends('name', 'ref')
    def _compute_full_name(self):
        for rec in self:
            name = "%s" % rec.name
            if (rec.ref):
                name = "%s (%s)" % (rec.name, rec.ref)
                
            rec.full_name = name

    @api.depends('invoice_ids')
    def _compute_is_my_customer(self):
        """计算客户是否属于当前公司的客户"""
        current_company = self.env.company
        for partner in self:
            # 检查该客户是否有当前公司的发票记录
            has_invoices = self.env['account.move'].search_count([
                ('partner_id', '=', partner.id),
                ('company_id', '=', current_company.id),
                ('move_type', 'in', ['out_invoice', 'out_refund'])
            ]) > 0
            partner.is_my_customer = has_invoices

    def _search_is_my_customer(self, operator, value):
        """搜索方法：根据客户是否属于当前公司进行过滤"""
        current_company = self.env.company
        
        # 获取所有有当前公司发票的客户ID
        customer_ids = self.env['account.move'].search([
            ('company_id', '=', current_company.id),
            ('move_type', 'in', ['out_invoice', 'out_refund'])
        ]).mapped('partner_id').ids
        
        if operator == '=' and value:
            # 搜索属于当前公司的客户
            return [('id', 'in', customer_ids)]
        elif operator == '=' and not value:
            # 搜索不属于当前公司的客户
            return [('id', 'not in', customer_ids)]
        elif operator == '!=' and value:
            # 搜索不属于当前公司的客户
            return [('id', 'not in', customer_ids)]
        elif operator == '!=' and not value:
            # 搜索属于当前公司的客户
            return [('id', 'in', customer_ids)]
        
        return []

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

        # 根据公司设置调整搜索条件(专门用于dymac的跨公司调货特殊情形)
        if current_company.private_contact_only:
            # 查找所有 is_virtual=True 的公司，并获取它们的 partner_id
            virtual_companies = self.env['res.company'].search([('is_virtual', '=', True)])
            special_partners = self.browse(virtual_companies.mapped('partner_id').ids)

            # 如果找到这些特殊 partners，将它们添加到结果集中
            if special_partners:
                recs |= special_partners

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