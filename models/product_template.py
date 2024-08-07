# -*- coding: UTF-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    inventory_type = fields.Selection([
        ('Stock', 'Stock'),
        ('Non-Stock', 'Non-Stock'),
        ('MRP', 'MRP'),
    ], string='Inventory Type', default=None, help="Label for stock management")

    secondary_uom_enabled = fields.Boolean("Enable Secondary UoM?")
    secondary_uom_id = fields.Many2one('uom.uom', 'Secondary UoM')
    secondary_uom_rate = fields.Float('Secondary Unit Rate', default=1)
    secondary_uom_name = fields.Char(
        "Secondary Unit",
        related='secondary_uom_id.name'
    )
    secondary_uom_desc = fields.Char(string='Secondary UoM Desc', compute='_compute_secondary_uom_desc', store=False)

    pack_supported = fields.Boolean("Support packaging", default=False)

    @api.depends('secondary_uom_enabled', 'uom_id', 'secondary_uom_id', 'secondary_uom_rate')
    def _compute_secondary_uom_desc(self):
        for rec in self:
            if rec.secondary_uom_enabled:
                rec.secondary_uom_desc = "1%s = %s%s" % (rec.secondary_uom_id.name, rec.secondary_uom_rate, rec.uom_id.name)
            else:
                rec.secondary_uom_desc = ""

    # def action_open_sh_quants(self):
    #     if self:
    #         for data in self:
    #             products = data.mapped('product_variant_ids')
    #             action = data.env.ref('stock.product_open_quants').read()[0]
    #             action['domain'] = [('product_id', 'in', products.ids)]
    #             action['context'] = {'search_default_internal_loc': 1}
    #             return action

    combined_name = fields.Char(string='Full Name', compute='_compute_combined_name', store=True)

    @api.depends('name')
    def _compute_combined_name(self):
        for product in self:
            names = []
            installed_langs = self.env["res.lang"].get_installed()
            for code, _ in installed_langs:
                product_lang = product.with_context(lang=code)
                names.append(product_lang.name)
            product.combined_name = ' / '.join(names)  # 使用 ' / ' 作为分隔符

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        domain = domain or []
        current_company = self.env.company

        # 检查当前公司是否设置了只看私有产品
        if current_company.private_product_only:
            domain += [('company_id', '=', current_company.id)]

        return super(ProductTemplate, self).search_read(domain=domain, fields=fields, offset=offset, limit=limit, order=order)