# -*- coding: UTF-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    secondary_uom = fields.Many2one('uom.uom', 'Secondary UOM')
    secondary_uom_name = fields.Char(
        "Secondary UOM",
        related='sh_secondary_uom.name'
    )
    secondary_unit_enabled = fields.Boolean("Enable Secondary Unit?")
    secondary_uom_rate = fields.Float('Rate to Primary Unit')

    # def action_open_sh_quants(self):
    #     if self:
    #         for data in self:
    #             products = data.mapped('product_variant_ids')
    #             action = data.env.ref('stock.product_open_quants').read()[0]
    #             action['domain'] = [('product_id', 'in', products.ids)]
    #             action['context'] = {'search_default_internal_loc': 1}
    #             return action