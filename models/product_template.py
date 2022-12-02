# -*- coding: UTF-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    secondary_uom_enabled = fields.Boolean("Enable Counting Unit?")
    secondary_uom_id = fields.Many2one('uom.uom', 'Counting Unit')
    secondary_uom_rate = fields.Float('Counting Unit Rate', default=1)

    secondary_uom_desc = fields.Char(string='Counting Unit', compute='_compute_secondary_uom_desc', store=False)

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