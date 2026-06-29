# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.osv import expression
from odoo.tools.misc import format_datetime
import logging
_logger = logging.getLogger(__name__)

class StockQuantityHistory(models.TransientModel):
    _inherit = 'stock.quantity.history'

    def open_at_date(self):
        _logger.info("***** StockQuantityHistory: open_at_date ****")
        _logger.info(self.env.company)
        
        tree_view_id = self.env.ref('stock.view_stock_product_tree').id
        form_view_id = self.env.ref('stock.product_form_view_procurement_button').id
        domain = [('type', '=', 'product')]
        # 共享产品的 company_id 为空，必须一并纳入，否则只会显示绑定了具体公司的产品。
        # 仅当公司开启“只看私有产品”时，才严格限定到本公司（与 product.product._name_search 保持一致）。
        if self.env.company.private_product_only:
            domain = expression.AND([domain, [('company_id', '=', self.env.company.id)]])
        else:
            domain = expression.AND([domain, ['|', ('company_id', '=', self.env.company.id), ('company_id', '=', False)]])
        product_id = self.env.context.get('product_id', False)
        product_tmpl_id = self.env.context.get('product_tmpl_id', False)
        if product_id:
            domain = expression.AND([domain, [('id', '=', product_id)]])
        elif product_tmpl_id:
            domain = expression.AND([domain, [('product_tmpl_id', '=', product_tmpl_id)]])
        # We pass `to_date` in the context so that `qty_available` will be computed across
        # moves until date.
        action = {
            'type': 'ir.actions.act_window',
            'views': [(tree_view_id, 'tree'), (form_view_id, 'form')],
            'view_mode': 'tree,form',
            'name': _('Products'),
            'res_model': 'product.product',
            'domain': domain,
            'context': dict(self.env.context, to_date=self.inventory_datetime),
            'display_name': format_datetime(self.env, self.inventory_datetime)
        }
        
        return action
