# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from datetime import datetime, time, timedelta
from odoo import SUPERUSER_ID, _, api, fields, models

_logger = logging.getLogger(__name__)

class StockWarehouseOrderpoint(models.Model):
    _inherit = "stock.warehouse.orderpoint"
    
    def action_cross_company_transfer(self):
        _logger.info("------------_auto_set_vendor------------")
        for record in self:
            _logger.info(record.id)

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
        _logger.info('*******---*stock.warehouse.orderpoint*---********')
        rec = super(StockWarehouseOrderpoint, self).create(vals)

        
        suppliers = rec.product_id.variant_seller_ids.filtered(lambda s: s.company_id.id == rec.company_id.id)
        if suppliers:
            # 如果只有一个供应商，那就直接填写上去
            if len(suppliers) ==1:
                rec.write({
                    'supplier_id': suppliers[0].id
                })
            else:
            # 如果有多个供应商，就选择最近采购的
                current_date = datetime.now().date()
                previous_date = current_date - timedelta(days=1)
                PurchaseOrderLineSudo = self.env['purchase.order.line'].sudo();
                #取消昨天的条件 ('create_date', '>=', previous_date)
                pol = PurchaseOrderLineSudo.search([('product_id', '=', rec.product_id.id), ('company_id', '=', rec.company_id.id), ('order_id.state', 'in', ['purchase', 'done'])], limit=1, order='create_date desc')
                if pol:
                    prevSuppliers = rec.product_id.variant_seller_ids.filtered(lambda s: s.name.id == pol.order_id.partner_id.id and s.company_id.id == rec.company_id.id)
                    if prevSuppliers:
                        rec.write({
                            'supplier_id': prevSuppliers[0].id
                        })
           
        return rec