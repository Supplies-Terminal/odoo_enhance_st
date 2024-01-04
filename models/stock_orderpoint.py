# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from datetime import datetime, time, timedelta
from odoo import SUPERUSER_ID, _, api, fields, models

_logger = logging.getLogger(__name__)

class StockWarehouseOrderpoint(models.Model):
    _inherit = "stock.warehouse.orderpoint"
    
    def action_replace(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('odoo_enhance_st.action_stock_orderpoint_replace')
        action['name'] = _('Replace %s', self.product_id.display_name)
        res = self.env['stock.orderpoint.replace'].create({
            'product_id': self.product_id.id,
        })
        action['res_id'] = res.id
        return action

    @api.depends('product_id')
    def _auto_set_vendor(self):
        for rec in self:
            rec.latest_vendor = ''
            _logger.info("------------_auto_set_vendor------------")
            current_date = datetime.now().date()
            previous_date = current_date - timedelta(days=1)
                        
            PurchaseOrderLineSudo = self.env['purchase.order.line'].sudo();
            pol = PurchaseOrderLineSudo.search([('product_id', '=', rec.product_id.id), ('order_id.state', 'in', ['purchase', 'done']), ('create_date', '>=', previous_date)], limit=1, order='create_date desc')
            if pol:
                _logger.info(pol.order_id.partner_id.name)
                suppliers = rec.product_id.suppliers.filtered(lambda s: s.partner_id.id == pol.order_id.partner_id.id)
                _logger.info(suppliers)
                if suppliers:
                    rec.supplier_id = suppliers[0].id

    @api.model
    def create(self, vals):
        # _logger.info('*******---*stock.warehouse.orderpoint*---********')
        rec = super(StockWarehouseOrderpoint, self).create(vals)
        # _logger.info(rec)
        # _logger.info(rec.product_id.variant_seller_ids)
        # _logger.info("------------_auto_set_vendor------------")
        # current_date = datetime.now().date()
        # previous_date = current_date - timedelta(days=1)
        # _logger.info("-----1------")
        # PurchaseOrderLineSudo = self.env['purchase.order.line'].sudo();
        # pol = PurchaseOrderLineSudo.search([('product_id', '=', rec.product_id.id), ('order_id.state', 'in', ['purchase', 'done']), ('create_date', '>=', previous_date)], limit=1, order='create_date desc')
        # _logger.info("-----2------")
        # if pol:
        #     _logger.info("-----3------")
        #     _logger.info(pol)
        #     suppliers = rec.product_id.variant_seller_ids.filtered(lambda s: s.name.id == pol.order_id.partner_id.id)
        #     _logger.info("-----4------")
        #     _logger.info(suppliers)
        #     if suppliers:
        #         rec.write({
        #             'supplier_id': suppliers[0].id
        #         })
           
        return rec