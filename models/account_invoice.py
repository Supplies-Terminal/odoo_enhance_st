# -*- coding: UTF-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from pytz import timezone
from datetime import datetime, time
import pytz

import logging
_logger = logging.getLogger(__name__)


class AccountInvoice(models.Model):
    _inherit = 'account.move'

    operating_company_id = fields.Many2one('res.company', index=True, string='Operating Company', required=False, domain=[('is_virtual', '=', True)])
    is_sales_company = fields.Boolean(string='Current Company is Virtual', compute='_compute_is_sales_company')
    @api.depends('company_id')
    def _compute_is_sales_company(self):
        for order in self:
            if order.company_id:
                order.is_sales_company = order.company_id.private_product_only == False and order.company_id.private_contact_only == False
            else:
                order.is_sales_company = False

    # @api.model
    # def create(self, vals):
    #     move = super(AccountInvoice, self).create(vals)
    #     if move.operating_company_id:
    #         move._update_daily_settlement()
    #     return move

    def write(self, vals):
        res = super(AccountInvoice, self).write(vals)
        for record in self:
            if record.operating_company_id:
                record._update_daily_settlement()
        return res

    def _get_product_and_accounts(self, company, product_name, account_type):
        """
        获取商品及其科目和税务。
        """
        product = self.env['product.product'].with_company(company.id).search([
            ('name', '=', product_name)
        ], limit=1)
        if not product:
            raise UserError(f"Product '{product_name}' is not available for company {company.name}.")
        
        if account_type == 'income':
            account = product.property_account_income_id or \
                      product.categ_id.with_company(company.id).property_account_income_categ_id
            taxes = product.taxes_id.filtered(lambda tax: tax.company_id == company)
        elif account_type == 'expense':
            account = product.property_account_expense_id or \
                      product.categ_id.with_company(company.id).property_account_expense_categ_id
            taxes = product.supplier_taxes_id.filtered(lambda tax: tax.company_id == company)
        else:
            raise ValueError("Invalid account_type. Use 'income' or 'expense'.")
        
        return product, account, taxes

    def _get_settlement_move(self, company, move_type, partner_id, origin, date):
        """
        查询结算发票或账单。
        """
        return self.env['account.move'].sudo().search([
            ('company_id', '=', company.id),
            ('move_type', '=', move_type),
            ('invoice_date', '=', date),
            ('partner_id', '=', partner_id),
            ('invoice_origin', '=', origin),
            ('state', '=', 'draft'),
        ], limit=1)

    def _update_daily_settlement(self):
        """更新每日结算单"""
        _logger.info("-----更新每日结算单--------")
        for record in self:
            settlement_date = record.invoice_date
            if not settlement_date:
                continue
    
            operating_company = record.operating_company_id
            sales_company = record.company_id

            _logger.info(f"Invoice: {record.id} {record.name} {record.invoice_date}")
            
            _logger.info(f"Operating company: {operating_company.id} {operating_company.name}")
            _logger.info(f"Sales company: {sales_company.id} {sales_company.name}")
    
            # 查询结算发票和账单
            settlement_invoice = self._get_settlement_move(
                operating_company, 'out_invoice', sales_company.partner_id.id, 'Daily Settlement', settlement_date
            )
            settlement_bill = self._get_settlement_move(
                sales_company, 'in_invoice', operating_company.partner_id.id, 'Daily Settlement', settlement_date
            )
    
            # 如果存在草稿状态的发票或账单，先删除
            if settlement_invoice:
                _logger.info(f"Deleting existing Invoice: {settlement_invoice.id}")
                settlement_invoice.unlink()
            if settlement_bill:
                _logger.info(f"Deleting existing Bill: {settlement_bill.id}")
                settlement_bill.unlink()
    
            # 获取所有相关的发票行，而不是全局的 move lines
            all_invoices = self.env['account.move'].search([
                ('company_id', '=', sales_company.id),
                ('invoice_date', '=', settlement_date),
                ('operating_company_id', '=', operating_company.id),
                ('state', '=', 'posted'),
            ])
            
            # 合并所有相关发票的 invoice_line_ids
            all_invoice_lines = all_invoices.mapped('invoice_line_ids')

            # 计算含税和不含税的总金额
            total_amount_tax = sum(line.price_subtotal for line in all_invoice_lines if line.tax_ids)
            total_amount_notax = sum(line.price_subtotal for line in all_invoice_lines if not line.tax_ids)
    
            _logger.info(f"Total Amount with Tax: {total_amount_tax}, Total Amount without Tax: {total_amount_notax}")
    
            # 扣减已过账的发票部分
            posted_invoices = self.env['account.move'].search([
                ('company_id', '=', operating_company.id),
                ('move_type', '=', 'out_invoice'),
                ('invoice_date', '=', settlement_date),
                ('partner_id', '=', sales_company.partner_id.id),
                ('invoice_origin', '=', 'Daily Settlement'),
                ('state', '=', 'posted'),
            ])
            posted_amount_tax_invoice = sum(
                line.price_unit for invoice in posted_invoices for line in invoice.invoice_line_ids if line.tax_ids
            )
            posted_amount_notax_invoice = sum(
                line.price_unit for invoice in posted_invoices for line in invoice.invoice_line_ids if not line.tax_ids
            )
    
            total_amount_tax_invoice = total_amount_tax - posted_amount_tax_invoice
            total_amount_notax_invoice = total_amount_notax - posted_amount_notax_invoice
    
            # 扣减已过账的账单部分
            posted_bills = self.env['account.move'].search([
                ('company_id', '=', sales_company.id),
                ('move_type', '=', 'in_invoice'),
                ('invoice_date', '=', settlement_date),
                ('partner_id', '=', operating_company.partner_id.id),
                ('invoice_origin', '=', 'Daily Settlement'),
                ('state', '=', 'posted'),
            ])
            posted_amount_tax_bill = sum(
                line.price_unit for bill in posted_bills for line in bill.invoice_line_ids if line.tax_ids
            )
            posted_amount_notax_bill = sum(
                line.price_unit for bill in posted_bills for line in bill.invoice_line_ids if not line.tax_ids
            )
    
            total_amount_tax_bill = total_amount_tax - posted_amount_tax_bill
            total_amount_notax_bill = total_amount_notax - posted_amount_notax_bill
    
            # 创建新发票
            _logger.info("Creating new Invoice")
            product_with_tax, income_account_tax, taxes = self._get_product_and_accounts(
                operating_company, 'Daily Settlement Products with TAX', 'income'
            )
            product_without_tax, income_account_notax, _ = self._get_product_and_accounts(
                operating_company, 'Daily Settlement Products without TAX', 'income'
            )
            operating_journal = self.env['account.journal'].sudo().search([
                ('type', '=', 'sale'),
                ('company_id', '=', operating_company.id)
            ], limit=1)
    
            invoice_vals = {
                'move_type': 'out_invoice',
                'partner_id': sales_company.partner_id.id,
                'company_id': operating_company.id,
                'journal_id': operating_journal.id,
                'invoice_date': settlement_date,
                'invoice_origin': 'Daily Settlement',
                'invoice_line_ids': [
                    (0, 0, {
                        'product_id': product_with_tax.id,
                        'quantity': 1.0,
                        'price_unit': total_amount_tax_invoice / (1 + sum(tax.amount/100.0 for tax in taxes)) if taxes else total_amount_tax_invoice,
                        'name': product_with_tax.name,
                        'account_id': income_account_tax.id,
                        'tax_ids': [(6, 0, taxes.ids)] if taxes else []
                    }),
                    (0, 0, {
                        'product_id': product_without_tax.id,
                        'quantity': 1.0,
                        'price_unit': total_amount_notax_invoice,
                        'name': product_without_tax.name,
                        'account_id': income_account_notax.id,
                        'tax_ids': []
                    })
                ]
            }
            settlement_invoice = self.env['account.move'].with_company(operating_company.id).create(invoice_vals)
    
            # 创建新账单
            _logger.info("Creating new Bill")
            product_with_tax_sales, expense_account_tax, supplier_taxes = self._get_product_and_accounts(
                sales_company, 'Daily Settlement Products with TAX', 'expense'
            )
            product_without_tax_sales, expense_account_notax, _ = self._get_product_and_accounts(
                sales_company, 'Daily Settlement Products without TAX', 'expense'
            )
            sales_journal = self.env['account.journal'].sudo().search([
                ('type', '=', 'purchase'),
                ('company_id', '=', sales_company.id)
            ], limit=1)
    
            bill_vals = {
                'move_type': 'in_invoice',
                'partner_id': operating_company.partner_id.id,
                'company_id': sales_company.id,
                'journal_id': sales_journal.id,
                'invoice_date': settlement_date,
                'invoice_origin': 'Daily Settlement',
                'invoice_line_ids': [
                    (0, 0, {
                        'product_id': product_with_tax_sales.id,
                        'quantity': 1.0,
                        'price_unit': total_amount_tax_bill / (1 + sum(tax.amount/100.0 for tax in supplier_taxes)) if supplier_taxes else total_amount_tax_bill,
                        'name': product_with_tax_sales.name,
                        'account_id': expense_account_tax.id,
                        'tax_ids': [(6, 0, supplier_taxes.ids)] if supplier_taxes else []
                    }),
                    (0, 0, {
                        'product_id': product_without_tax_sales.id,
                        'quantity': 1.0,
                        'price_unit': total_amount_notax_bill,
                        'name': product_without_tax_sales.name,
                        'account_id': expense_account_notax.id,
                        'tax_ids': []
                    })
                ]
            }
            settlement_bill = self.env['account.move'].with_company(sales_company.id).create(bill_vals)
                
    def _set_next_sequence(self):
        if self.move_type == 'out_invoice':
            if not self.company_id.private_contact_only and not self.company_id.private_product_only and not self.company_id.is_virtual:
                _logger.info("销售公司使用virtual company序列号")
                # 检查前置条件
                invoices = self.env['account.move'].sudo().search([
                    ('company_id.is_virtual', '=', True),
                    ('invoice_user_id', '=', 2),
                    ('payment_reference', '=', 'SO_SEQUENCE'),
                ], order='name desc')
                
                if not invoices or len(invoices) < 2:
                    raise UserError('No SO_SEQUENCE found for invoices (at least 2) in virtual company')

                toronto_timezone = pytz.timezone('America/Toronto')
                now_utc = datetime.utcnow().replace(tzinfo=pytz.utc)
                now_toronto = now_utc.astimezone(toronto_timezone)
            
                invoice = invoices[1]
                invoice.button_draft()
                invoice.write({
                    'name': 'draft',
                    'date': now_toronto
                })
                _logger.info(invoice.name)
                invoice._set_next_sequence()

                # 使用虚拟公司生成的序列号
                self.name = invoice.name
                _logger.info(self.name)
            else:
                _logger.info("非销售公司，使用自己的序列号")
                super(AccountInvoice, self)._set_next_sequence()
        else:
            super(AccountInvoice, self)._set_next_sequence()
            
    def _prepare_invoice_line_from_po_line(self, line):
        res = super(AccountInvoice,
                    self)._prepare_invoice_line_from_po_line(line)
        res.update({
            'secondary_qty': line.secondary_qty,
            'secondary_uom': line.secondary_uom.id,
        })
        return res

    def action_post(self):
        # 调用父类的 action_post 方法
        super(AccountInvoice, self).action_post()

        # 对于每个发票，将其日期设置为对应销售订单的订单日期
        for record in self:
            # 检查是否存在源销售订单
            if record.invoice_origin:
                sale_order = self.env['sale.order'].search([('name', '=', record.invoice_origin)], limit=1)
                if sale_order and sale_order.date_order:
                    # 将发票日期设置为销售订单的日期
                    # 考虑时区转换
                    # user_tz = self.env.user.tz or self.env.context.get('tz')
                    # if user_tz:
                    #     local = timezone(user_tz)
                    #     local_dt = local.localize(fields.Datetime.from_string(sale_order.date_order), is_dst=None)
                    #     utc_dt = local_dt.astimezone(timezone('UTC'))
                    #     record.write({
                    #         'invoice_date': utc_dt,
                    #         'invoice_date_due': utc_dt,
                    #     })
                    # else:
                    #     # 如果无法确定时区，则直接使用订单日期
                    
                    # UTC时间转换为多伦多时间
                    record.write({
                        'invoice_date': sale_order.date_order.astimezone(timezone('america/toronto')).date(),
                        'invoice_date_due': sale_order.date_order.astimezone(timezone('america/toronto')).date(),
                    })

class AccountInvoiceLine(models.Model):
    _inherit = "account.move.line"

    secondary_qty = fields.Float("Secondary QTY", digits='Product Unit of Measure')
    secondary_uom_id = fields.Many2one("uom.uom", 'Secondary UoM', compute='_compute_secondary_uom_id', store=True)
    secondary_uom_name = fields.Char("Secondary Unit", compute='_compute_secondary_uom_name', store=True)
    secondary_uom_enabled = fields.Boolean("Secondary UoM Enabled?", compute='_compute_secondary_uom_enabled', store=True)
    secondary_uom_rate = fields.Float( "Secondary Unit Rate", compute='_compute_secondary_uom_rate', store=True)
    secondary_uom_desc = fields.Char(string='Secondary Unit Desc', compute='_compute_secondary_uom_desc', store=True)
    description_with_counts = fields.Char(string='Item Description', compute='_compute_description_with_counts', store=True)

    @api.depends('product_id')
    def _compute_secondary_uom_id(self):
        for rec in self:
            if rec.product_id.secondary_uom_enabled and rec.product_id.secondary_uom_id:
                rec.secondary_uom_id = rec.product_id.secondary_uom_id.id
            # else:
            #     rec.secondary_uom_id = 

    @api.depends('product_id')
    def _compute_secondary_uom_name(self):
        for rec in self:
            if rec.product_id.secondary_uom_enabled:
                rec.secondary_uom_name = rec.product_id.secondary_uom_name
            else:
                rec.secondary_uom_name = ""

    @api.depends('product_id')
    def _compute_secondary_uom_rate(self):
        for rec in self:
            if rec.product_id.secondary_uom_enabled:
                rec.secondary_uom_rate = rec.product_id.secondary_uom_rate
            else:
                rec.secondary_uom_rate = 0.00

    @api.depends('product_id')
    def _compute_secondary_uom_enabled(self):
        for rec in self:
            rec.secondary_uom_enabled = rec.product_id.secondary_uom_enabled

                
    @api.depends('secondary_uom_enabled', 'product_uom_id', 'secondary_uom_id', 'secondary_uom_rate')
    def _compute_secondary_uom_desc(self):
        for rec in self:
            if rec.secondary_uom_enabled:
                rec.secondary_uom_desc = "%s (%s %s)" % (rec.secondary_uom_name, rec.secondary_uom_rate, rec.product_uom_id.name)
            else:
                rec.secondary_uom_desc = ""

    @api.depends('secondary_uom_enabled', 'secondary_qty')
    def _compute_description_with_counts(self):
        for rec in self:
            if rec.secondary_uom_enabled:
                rec.description_with_counts = "%s (%s %s)" % (rec.name, rec.secondary_qty, rec.secondary_uom_name)
            else:
                rec.description_with_counts = rec.name

    @api.onchange('secondary_qty')
    def onchange_secondary_qty(self):
        if self and self.secondary_uom_enabled and self.product_uom_id:
            if self.quantity:
                self.quantity = self.secondary_qty * self.secondary_uom_rate
            else:
                self.quantity = 0

    @api.onchange('product_id')
    def onchange_secondary_uom(self):
        if self:
            for rec in self:
                if rec.product_id:
                    if rec.product_id.secondary_uom_enabled and rec.product_id.secondary_uom_id:
                        rec.secondary_uom_id = rec.product_id.secondary_uom_id.id
                        rec.quantity = rec.secondary_qty * rec.product_id.secondary_uom_rate
                    else:
                        rec.secondary_qty = 0.0
                        rec.quantity = 0.0
                else:
                    rec.secondary_qty = 0.0
                    rec.quantity = 0.0
               