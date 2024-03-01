# -*- coding: UTF-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields

class CustomMrpBomLine(models.Model):
    _inherit = 'mrp.bom.line'  # 或者是 'mrp.bom' 如果是 BOM本身的数量

    product_qty = fields.Float(digits=(16, 3))  # 设置为16位整数和3位小数
