# -*- coding: utf-8 -*-
from odoo import fields, models


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    # 从产品模板获取volume字段
    product_volume = fields.Float(
        string='Volume',
        related='product_id.volume',
        readonly=True,
        store=False,
    )

