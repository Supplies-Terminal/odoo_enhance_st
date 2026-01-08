# -*- coding: UTF-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api
from datetime import datetime, date


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

    latest_cost = fields.Char(string='Latest Cost', compute='_compute_latest_cost', store=False)

    @api.depends('secondary_uom_enabled', 'uom_id', 'secondary_uom_id', 'secondary_uom_rate')
    def _compute_secondary_uom_desc(self):
        for rec in self:
            if rec.secondary_uom_enabled:
                rec.secondary_uom_desc = "1%s = %s%s" % (rec.secondary_uom_id.name, rec.secondary_uom_rate, rec.uom_id.name)
            else:
                rec.secondary_uom_desc = ""

    @api.depends('product_variant_ids')
    def _compute_latest_cost(self):
        for rec in self:
            cost_info = []
            # 获取所有公司
            companies = self.env['res.company'].search([('id', '=', 9)])
            
            for company in companies:
                # 获取该公司的采购订单行
                PurchaseOrderLine = self.env['purchase.order.line'].sudo()
                BillLine = self.env['account.move.line'].sudo()
                
                # 获取当前日期
                current_date = fields.Date.today()
                
                # 搜索采购订单行
                pol = PurchaseOrderLine.sudo().search([
                    ('product_id.product_tmpl_id', '=', rec.id),
                    ('order_id.company_id', '=', company.id),
                    ('order_id.state', 'in', ['purchase', 'done']),
                    ('order_id.date_approve', '<=', current_date)
                ])
                # 手动排序并取第一条
                if pol:
                    pol = sorted(pol, key=lambda x: x.order_id.date_approve or datetime.min, reverse=True)
                    pol = pol[0] if pol else None
                
                # 搜索供应商账单行
                bill = BillLine.search([
                    ('product_id.product_tmpl_id', '=', rec.id),
                    ('move_id.company_id', '=', company.id),
                    ('move_id.state', '=', 'posted'),
                    ('move_id.move_type', '=', 'in_invoice'),
                    ('move_id.invoice_date', '<=', current_date)
                ])
                # 手动排序并取第一条
                if bill:
                    bill = sorted(bill, key=lambda x: x.move_id.invoice_date or datetime.min, reverse=True)
                    bill = bill[0] if bill else None
                
                # 确定最近的采购或账单
                pol_date = pol.order_id.date_approve if pol and pol.order_id.date_approve else datetime.min
                bill_date = bill.move_id.invoice_date if bill and bill.move_id.invoice_date else datetime.min
                
                # 确保日期类型一致，都转换为 datetime 对象
                if isinstance(pol_date, date):
                    pol_date = datetime.combine(pol_date, datetime.min.time())
                if isinstance(bill_date, date):
                    bill_date = datetime.combine(bill_date, datetime.min.time())

                if pol_date >= bill_date and pol:
                    latest_line = pol
                elif bill:
                    latest_line = bill
                else:
                    latest_line = None
                    
                if latest_line:
                    if 'purchase.order.line' in latest_line._name:
                        cost_info.append(f"${latest_line.price_unit}/{latest_line.product_uom.name}")
                    elif 'account.move.line' in latest_line._name:
                        cost_info.append(f"${latest_line.price_unit}/{latest_line.product_uom_id.name}")
            
            rec.latest_cost = '\n'.join(cost_info) if cost_info else '-'

    # def action_open_sh_quants(self):
    #     if self:
    #         for data in self:
    #             products = data.mapped('product_variant_ids')
    #             action = data.env.ref('stock.product_open_quants').read()[0]
    #             action['domain'] = [('product_id', 'in', products.ids)]
    #             action['context'] = {'search_default_internal_loc': 1}
    #             return action

    combined_name = fields.Char(string='Full Name', compute='_compute_combined_name', store=True)

    def action_view_stock_valuation(self):
        """打开该产品的 Stock Valuation 页面"""
        self.ensure_one()
        # 获取产品变体的 IDs
        product_ids = self.product_variant_ids.ids
        
        return {
            'name': f'Stock Valuation - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'stock.valuation.layer',
            'view_mode': 'tree,form',
            'domain': [('product_id', 'in', product_ids)],
            'context': {'search_default_product_id': product_ids[0] if product_ids else False},
            'target': 'current',
        }

    last_vendor_id = fields.Many2one('res.partner', string='Last Vendor', 
        compute='_compute_last_vendor_id', store=True, 
        help="The last vendor who supplied this product in the current company")

    @api.depends('product_variant_ids', 'product_variant_ids.purchase_order_line_ids.order_id.state')
    def _compute_last_vendor_id(self):
        for rec in self:
            # 只支持单一的公司（因为需要搜索和排序，只能是storable字段，存储单一的值）
            company_id = 9
            # 获取当前公司的采购订单行
            PurchaseOrderLine = self.env['purchase.order.line'].sudo()
            BillLine = self.env['account.move.line'].sudo()
            
            # 获取当前日期
            current_date = fields.Date.today()
            
            # 搜索采购订单行
            pol = PurchaseOrderLine.sudo().search([
                ('product_id.product_tmpl_id', '=', rec.id),
                ('order_id.company_id', '=', company_id),
                ('order_id.state', 'in', ['purchase', 'done']),
                ('order_id.date_approve', '<=', current_date)
            ])
            # 手动排序并取第一条
            if pol:
                pol = sorted(pol, key=lambda x: x.order_id.date_approve or datetime.min, reverse=True)
                pol = pol[0] if pol else None
            
            # 搜索供应商账单行
            bill = BillLine.search([
                ('product_id.product_tmpl_id', '=', rec.id),
                ('move_id.company_id', '=', company_id),
                ('move_id.state', '=', 'posted'),
                ('move_id.move_type', '=', 'in_invoice'),
                ('move_id.invoice_date', '<=', current_date)
            ])
            # 手动排序并取第一条
            if bill:
                bill = sorted(bill, key=lambda x: x.move_id.invoice_date or datetime.min, reverse=True)
                bill = bill[0] if bill else None
            
            # 确定最近的采购或账单
            pol_date = pol.order_id.date_approve if pol and pol.order_id.date_approve else datetime.min
            bill_date = bill.move_id.invoice_date if bill and bill.move_id.invoice_date else datetime.min
            
            # 确保日期类型一致，都转换为 datetime 对象
            if isinstance(pol_date, date):
                pol_date = datetime.combine(pol_date, datetime.min.time())
            if isinstance(bill_date, date):
                bill_date = datetime.combine(bill_date, datetime.min.time())

            if pol_date >= bill_date and pol:
                latest_line = pol
            elif bill:
                latest_line = bill
            else:
                latest_line = None           
                 
            if latest_line:
                if 'purchase.order.line' in latest_line._name:
                    rec.last_vendor_id = latest_line.order_id.partner_id
                elif 'account.move.line' in latest_line._name:
                    rec.last_vendor_id = latest_line.move_id.partner_id
            else:
                rec.last_vendor_id = False

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