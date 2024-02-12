# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from datetime import datetime, time, timedelta
from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

class StockWarehouseOrderpoint(models.Model):
    _inherit = "stock.warehouse.orderpoint"
    
    def action_cross_company_transfer(self):
        _logger.info("------------action_cross_company_transfer------------")
    
        # 使用字典来创建跨公司调拨清单
        transfer_dict = {}
    
        for record in self:
            _logger.info(record.id)
            _logger.info(record.vendor_id)
            
            # 根据需求量和可用量决定最终调货量
            that_company = None
            available_stock = 0

            if record.vendor_id:
                that_company = self.env['res.company'].search([('partner_id', '=', record.vendor_id.id)], limit=1)
                if that_company:
                    available_stock = record.product_id.with_company(that_company.id).qty_available
        
            qty_to_order = min(available_stock, record.qty_to_order)
    
            # 要调入的仓库位置
            this_warehouse = record.warehouse_id
            if not this_warehouse:
                raise UserError(f"No warehouse found. Skipping...")
                return
            this_location = this_warehouse.lot_stock_id
            this_company =  this_warehouse.company_id


            # 获取特定公司的供应商位置
            vendor_location = self.env['stock.location'].sudo().search([('usage', '=', 'supplier')], limit=1)

            if not vendor_location:
                raise UserError(f"No vendor location found. Skipping...")
                return
            
            # 获取特定公司的客户位置
            customer_location = self.env['stock.location'].sudo().search([('usage', '=', 'customer')], limit=1)
            if not customer_location:
                raise UserError(f"No customer location found. Skipping...")
                return
                
            _logger.info(this_company.name)
            _logger.info(this_warehouse.name)
            _logger.info(this_location.name)
            _logger.info(vendor_location.name)
            _logger.info("-------")

            if that_company and qty_to_order > 0:
                product = record.product_id

                # 根据公司加入到字典中，用于按公司创建invoice和bill
                if that_company.id not in transfer_dict:
                    transfer_dict[that_company.id] = []
                    
                transfer_dict[that_company.id].append({
                    "product": product,
                    "quantity": qty_to_order
                    });

                # 确定调入的仓库位置
                that_warehouse = self.env['stock.warehouse'].sudo().search([('company_id', '=', that_company.id)], limit=1)
                if not that_warehouse:
                    raise UserError(f"No warehouse found for company {that_company.id}. Skipping...")
                    return
                that_location = that_warehouse.lot_stock_id


                _logger.info(that_company.name)
                _logger.info(that_warehouse.name)
                _logger.info(that_location.name)
                _logger.info(customer_location.name)
                _logger.info("-------")

                # 执行调出：减少采购公司库存
                move_out_values = {
                    'name': product.name,
                    'product_id': product.id,
                    'product_uom_qty': qty_to_order,
                    'product_uom': product.uom_id.id,
                    'location_id': that_location.id,  # 调出公司的库存位置
                    'location_dest_id': customer_location.id,  # 调出公司的客户位置
                    'company_id': that_company.id,
                    'origin': '跨公司调拨'
                }
                _logger.info(move_out_values)
                stock_move_out = self.env['stock.move'].with_context(default_company_id = that_company.id).sudo().create(move_out_values)

                if stock_move_out:
                    _logger.info(stock_move_out)
                    _logger.info(stock_move_out.name)
                    stock_move_out._action_confirm()
                    stock_move_out._action_assign()
                    stock_move_out.move_line_ids.qty_done = qty_to_order
                    stock_move_out._action_done()

                # 执行调入：增加本公司库存
                move_in_values = {
                    'name': product.name,
                    'product_id': product.id,
                    'product_uom_qty': qty_to_order,
                    'product_uom': product.uom_id.id,
                    'location_id': vendor_location.id,  # 调入公司的供应商位置
                    'location_dest_id': this_location.id,  # 调入公司的库存位置
                    'company_id': this_company.id,
                    'origin': '跨公司调拨'
                }
                _logger.info(move_in_values)
                stock_move_in = self.env['stock.move'].with_context(default_company_id = this_company.id).sudo().create(move_in_values)

                if stock_move_in:
                    _logger.info(stock_move_in)
                    _logger.info(stock_move_in.name)
                    stock_move_in._action_confirm()
                    stock_move_in._action_assign()
                    stock_move_in.move_line_ids.qty_done = qty_to_order
                    stock_move_in._action_done()
                
        _logger.info(transfer_dict)
        
        # for company_id in transfer_dict:
            # 增加本公司库存的逻辑
            # 创建发票和账单的逻辑
        # 循环处理transfer_dict以创建账单和发票
        current_date = datetime.now().date()
        for that_company_id, lines in transfer_dict.items():
            # 创建账单（供应商账单）
            out_partner_id = self.env['res.company'].browse(that_company_id).partner_id.id
            bill_vals = {
                'invoice_date': current_date,  # 发票日期
                'date': current_date,  # 记账日期
                'company_id': this_company.id,
                'move_type': 'in_invoice',  # 表示这是一张供应商账单
                'partner_id': out_partner_id,
                'invoice_line_ids': [],
                'ref': '跨公司调拨'
            }

            # 创建发票（客户发票）
            in_partner_id = self.env['res.company'].browse(this_company.id).partner_id.id
            invoice_vals = {
                'invoice_date': current_date,  # 发票日期
                'date': current_date,  # 记账日期
                'company_id': that_company_id,
                'move_type': 'out_invoice',  # 表示这是一张客户发票
                'partner_id': in_partner_id,
                'invoice_line_ids': [],
                'ref': '跨公司调拨'
            }

            for line in lines:
                product = line['product']
                price = self.get_latest_price(product.id, in_partner_id, that_company_id) # 该商品在转出的公司销售给转入公司的最后的价格
                quantity = line['quantity']

                # 填充账单行
                bill_line_vals = {
                    'name': product.name,
                    'product_id': product.id,
                    'product_uom_id': product.uom_id.id,
                    'quantity': quantity,
                    'price_unit': price,  # 采购价格
                }
                bill_vals['invoice_line_ids'].append((0, 0, bill_line_vals))

                # 填充发票行
                invoice_line_vals = {
                    'name': product.name,
                    'product_id': product.id,
                    'product_uom_id': product.uom_id.id,
                    'quantity': quantity,
                    'price_unit': price,  # 销售价格
                }
                invoice_vals['invoice_line_ids'].append((0, 0, invoice_line_vals))

            # 创建账单和发票记录
            _logger.info("------bill-------")
            _logger.info(bill_vals)
            bill = self.env['account.move'].with_context(default_company_id = bill_vals['company_id']).sudo().create(bill_vals)
            # bill.action_post()
            _logger.info(bill)

            _logger.info("------invoice-------")
            _logger.info(invoice_vals)
            invoice = self.env['account.move'].with_context(default_company_id = invoice_vals['company_id']).sudo().create(invoice_vals)
            # invoice.action_post()
            _logger.info(invoice)

        # 不能返回这个，否则不会自动刷新
        # message = _('Cross company purchasing successfully!')
        # return {
        #     'type': 'ir.actions.client',
        #     'tag': 'display_notification',
        #     'params': {
        #         'title': _('Success'),
        #         'message': message,
        #         'sticky': False,  # 消息不会一直停留在屏幕上
        #     }
        # }

    def get_latest_price(self, product_id, customer_id, company_id):
        price = 0

        OrderModel = self.env['sale.order']
        
        # 获取当前日期
        current_date = datetime.now().date()

        # # 以当前销售公司在采购公司的最后一次购买的价格为准
        # SaleOrderLineSudo = self.env['sale.order.line'].sudo();
        # sol = SaleOrderLineSudo.search([('product_id', '=', product_id), ('order_id.company_id', '=', company_id), ('order_id.partner_id', '=', customer_id), ('order_id.state', 'in', ['sale', 'done'])], limit=1, order='order_id desc')
        # if sol:
        #     price = sol.price_unit


        # 以采购公司的最后一次购入成本为准
        PurchaseOrderLineSudo = self.env['purchase.order.line'].sudo();
        pol = PurchaseOrderLineSudo.search([('product_id', '=', product_id), ('order_id.company_id', '=', company_id), ('order_id.state', 'in', ['purchase', 'done'])], limit=1, order='create_date desc')
        if pol:
            price = pol.price_unit

        return price
                    
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