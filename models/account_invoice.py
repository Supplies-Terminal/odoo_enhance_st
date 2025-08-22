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

    # 类级别的防重复锁
    _billing_update_locks = {}

    operating_company_id = fields.Many2one('res.company', index=True, string='Operating Company', required=False, domain=[('is_virtual', '=', True)])
    is_sales_company = fields.Boolean(string='Current Company is Virtual', compute='_compute_is_sales_company')
    @api.depends('company_id')
    def _compute_is_sales_company(self):
        for order in self:
            if order.company_id:
                order.is_sales_company = order.company_id.private_product_only == False and order.company_id.private_contact_only == False
            else:
                order.is_sales_company = False

    @api.model
    def create(self, vals):
        move = super(AccountInvoice, self).create(vals)
        if move.operating_company_id:
            move._update_daily_settlement()
        return move

    def write(self, vals):
        res = super(AccountInvoice, self).write(vals)
        for record in self:
            if record.operating_company_id:
                record._update_daily_settlement()
            
            # 只处理两个关键事件：reset to draft 和 confirm invoice
            if 'state' in vals:
                try:
                    if vals['state'] in ['draft', 'posted']:
                        # 统一处理发票状态变化
                        record._handle_invoice_state_change()
                except Exception as e:
                    _logger.error(f"处理发票 {record.id} 状态变化时出错: {str(e)}")
                    # 如果是不平衡账单错误或其他关键错误，应该阻止发票状态变化
                    if "unbalanced journal entry" in str(e) or "Cannot create" in str(e):
                        _logger.error(f"关键错误，阻止发票状态变化")
                        raise
                    else:
                        # 其他非关键错误只记录，不阻止发票状态变化
                        _logger.error(f"非关键错误，发票状态变化将继续，但账单更新可能失败")
        return res

    def _create_adjustment_bill(self, billing_company, mapping, invoice_date, adjustment_amount, total_amount_tax_bill, total_amount_notax_bill):
        """创建调整账单"""
        _logger.info(f"Creating adjustment bill for company {billing_company.id}, date {invoice_date}, amount {adjustment_amount}")
        
        # 获取产品和账户信息
        product_with_tax, expense_account_tax, supplier_taxes = self._get_product_and_accounts(
            billing_company, 'Daily Settlement Products with TAX', 'expense'
        )
        product_without_tax, expense_account_notax, _ = self._get_product_and_accounts(
            billing_company, 'Daily Settlement Products without TAX', 'expense'
        )
        
        # 获取采购日记账
        sales_journal = self.env['account.journal'].sudo().search([
            ('type', '=', 'purchase'),
            ('company_id', '=', billing_company.id)
        ], limit=1)
        
        # 使用映射中的billing_partner_id作为供应商
        vendor_partner_id = mapping.billing_partner_id.id
        
        # 准备调整账单行
        invoice_line_ids = []
        
        # 根据调整金额的正负决定是借方还是贷方
        if adjustment_amount > 0:
            # 需要增加金额：创建借方行
            if total_amount_tax_bill > 0:
                invoice_line_ids.append((0, 0, {
                    'product_id': product_with_tax.id,
                    'quantity': 1.0,
                    'price_unit': total_amount_tax_bill / (1 + sum(tax.amount/100.0 for tax in supplier_taxes)) if supplier_taxes else total_amount_tax_bill,
                    'name': f"Adjustment - {product_with_tax.name}",
                    'account_id': expense_account_tax.id,
                    'tax_ids': [(6, 0, supplier_taxes.ids)] if supplier_taxes else []
                }))
            
            if total_amount_notax_bill > 0:
                invoice_line_ids.append((0, 0, {
                    'product_id': product_without_tax.id,
                    'quantity': 1.0,
                    'price_unit': total_amount_notax_bill,
                    'name': f"Adjustment - {product_without_tax.name}",
                    'account_id': expense_account_notax.id,
                    'tax_ids': []
                }))
        else:
            # 需要减少金额：创建贷方行（负数）
            adjustment_amount = abs(adjustment_amount)
            if total_amount_tax_bill > 0:
                invoice_line_ids.append((0, 0, {
                    'product_id': product_with_tax.id,
                    'quantity': -1.0,  # 负数数量
                    'price_unit': total_amount_tax_bill / (1 + sum(tax.amount/100.0 for tax in supplier_taxes)) if supplier_taxes else total_amount_tax_bill,
                    'name': f"Adjustment - {product_with_tax.name}",
                    'account_id': expense_account_tax.id,
                    'tax_ids': [(6, 0, supplier_taxes.ids)] if supplier_taxes else []
                }))
            
            if total_amount_notax_bill > 0:
                invoice_line_ids.append((0, 0, {
                    'product_id': product_without_tax.id,
                    'quantity': -1.0,  # 负数数量
                    'name': f"Adjustment - {product_without_tax.name}",
                    'price_unit': total_amount_notax_bill,
                    'account_id': expense_account_notax.id,
                    'tax_ids': []
                }))
        
        # 创建调整账单
        adjustment_bill_vals = {
            'move_type': 'in_invoice',
            'partner_id': vendor_partner_id,
            'company_id': billing_company.id,
            'journal_id': sales_journal.id,
            'invoice_date': invoice_date,
            'invoice_line_ids': invoice_line_ids,
            'invoice_origin': 'Auto Billing',
            'ref': f'Adjustment for {invoice_date}',
        }
        
        adjustment_bill = self.env['account.move'].sudo().create(adjustment_bill_vals)
        _logger.info(f"Created adjustment bill: {adjustment_bill.id}")
        
        return adjustment_bill

    def unlink(self):
        return super(AccountInvoice, self).unlink()

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
                if settlement_invoice:
                    for line in settlement_invoice.line_ids:
                        if line.reconciled:
                            line.remove_move_reconcile()
                    if settlement_invoice.name != '/':
                        settlement_invoice.name = '/'
                    settlement_invoice.button_draft()
                    settlement_invoice.unlink()
            if settlement_bill:
                _logger.info(f"Deleting existing Bill: {settlement_bill.id}")
                if settlement_bill:
                    for line in settlement_bill.line_ids:
                        if line.reconciled:
                            line.remove_move_reconcile()
                    if settlement_bill.name != '/':
                        settlement_bill.name = '/'
                    settlement_bill.button_draft()
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
            total_amount_tax = sum(
                line.price_total
                for line in all_invoice_lines
                if line.tax_ids and any(tax.amount > 0 for tax in line.tax_ids)
            )
            total_amount_notax = sum(
                line.price_total
                for line in all_invoice_lines
                if not line.tax_ids or all(tax.amount == 0 for tax in line.tax_ids)
            )
    
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

    def _handle_invoice_state_change(self):
        """统一处理发票状态变化"""
        for record in self:
            # 处理销售发票和贷项通知单
            if record.move_type not in ['out_invoice', 'out_refund']:
                continue
            
            _logger.info(f"_handle_invoice_state_change处理发票状态变化: {record.id} {record.name} {record.invoice_date}")
            
            # 使用类级别的锁防止重复触发
            lock_key = f"invoice_state_{record.id}_{record.invoice_date}"
            if lock_key in self._billing_update_locks:
                _logger.info(f"跳过重复的发票状态变化处理: {record.id} {record.name} (锁已存在)")
                continue
            
            # 设置锁
            self._billing_update_locks[lock_key] = True
            
            try:
                # 检查是否存在客户账单映射关系
                mapping = self.env['customer.billing.mapping'].search([
                    ('company_id', '=', record.company_id.id),
                    ('partner_id', '=', record.partner_id.id),
                    ('active', '=', True)
                ], limit=1)
                
                if not mapping:
                    continue

                # 根据发票类型分别处理
                if record.move_type == 'out_invoice':
                    # 销售发票：使用原有的合并逻辑
                    _logger.info(f"处理销售发票，使用合并逻辑")
                    self._handle_sales_invoice_billing(record, mapping)
                else:
                    # 贷项通知单：使用一一对应逻辑
                    _logger.info(f"处理贷项通知单，使用一一对应逻辑")
                    self._handle_credit_note_billing(record, mapping)
                
                _logger.info(f"Completed billing update for invoice {record.name}")
                
            except Exception as e:
                _logger.error(f"处理发票状态变化时发生错误: {str(e)}")
                # 记录错误但不中断流程
            finally:
                # 清除锁
                if lock_key in self._billing_update_locks:
                    del self._billing_update_locks[lock_key]

    def _handle_sales_invoice_billing(self, record, mapping):
        """处理销售发票的账单逻辑（原有的合并逻辑）"""
        billing_company = mapping.billing_company_id
        invoice_date = record.invoice_date
        
        if not invoice_date:
            _logger.info(f"处理销售发票失败，没有invoice_date")
            return
        
        # 使用映射中的billing_partner_id作为供应商ID
        vendor_partner_id = mapping.billing_partner_id.id
        
        # 查找现有的账单
        existing_bills = self.env['account.move'].sudo().search([
            ('company_id', '=', billing_company.id),
            ('move_type', '=', 'in_invoice'),
            ('invoice_date', '=', invoice_date),
            ('partner_id', '=', vendor_partner_id),
            ('invoice_origin', '=', 'Auto Billing'),
            ('state', 'in', ['draft', 'posted']),
        ])
        
        if existing_bills:
            # 分类账单：已付款和未付款
            paid_bills = []
            unpaid_bills = []
            
            for bill in existing_bills:
                if bill.amount_residual < bill.amount_total:
                    paid_bills.append(bill)
                else:
                    unpaid_bills.append(bill)
            
            # 处理未付款账单
            if unpaid_bills:
                if len(unpaid_bills) > 1:
                    # 保留第一个未付款账单，删除其他的
                    for bill in unpaid_bills[1:]:
                        if bill.state == 'posted':
                            for line in bill.line_ids:
                                if line.reconciled:
                                    line.remove_move_reconcile()
                            bill.button_draft()
                        bill.unlink()
                
                # 更新第一个未付款账单
                existing_bill = unpaid_bills[0]
                self._update_customer_billing_bill(billing_company, record, mapping, existing_bill, paid_bills)
            else:
                self._update_customer_billing_bill(billing_company, record, mapping, False, paid_bills)
        else:
            # 如果没有现有账单，创建新的
            self._update_customer_billing_bill(billing_company, record, mapping, False, [])

    def _handle_credit_note_billing(self, record, mapping):
        """处理贷项通知单的账单逻辑（一一对应逻辑）"""
        billing_company = mapping.billing_company_id
        invoice_date = record.invoice_date
        
        if not invoice_date:
            _logger.info(f"处理贷项通知单失败，没有invoice_date")
            return
        
        # 使用映射中的billing_partner_id作为供应商ID
        vendor_partner_id = mapping.billing_partner_id.id
        
        # 检查是否已经存在对应的退款单
        existing_credit_bill = self.env['account.move'].sudo().search([
            ('company_id', '=', billing_company.id),
            ('move_type', '=', 'in_refund'),  # 门店端对应的是退款单，不是账单
            ('invoice_date', '=', invoice_date),
            ('partner_id', '=', vendor_partner_id),
            ('invoice_origin', '=', 'Auto Billing Credit Note'),
            ('ref', '=', record.name),  # 通过源文档号码匹配
            ('state', 'in', ['draft', 'posted']),
        ], limit=1)
        
        # 计算该贷项通知单的金额
        credit_tax_amount = 0
        credit_notax_amount = 0
        
        for line in record.invoice_line_ids:
            if line.tax_ids and any(tax.amount > 0 for tax in line.tax_ids):
                credit_tax_amount += line.price_total
            else:
                credit_notax_amount += line.price_total
        
        if existing_credit_bill:
            # 检查金额是否一致
            expected_total = credit_tax_amount + credit_notax_amount
            current_total = abs(existing_credit_bill.amount_total)  # 取绝对值，因为是负数
            
            _logger.info(f"Credit note {record.name}: expected={expected_total}, current={current_total}")
            
            if abs(expected_total - current_total) > 0.01:  # 允许小数点精度误差
                _logger.info(f"Amount mismatch for credit note {record.name}, updating refund {existing_credit_bill.id}")
                # 金额不一致，需要更新
                self._update_credit_note_refund(existing_credit_bill, record, credit_tax_amount, credit_notax_amount)
            else:
                _logger.info(f"Credit note {record.name} refund {existing_credit_bill.id} already exists with correct amount")
        else:
            # 不存在对应退款单，创建新的
            _logger.info(f"Creating new refund for credit note {record.name}")
            self._create_credit_note_refund(record, credit_tax_amount, credit_notax_amount, 
                                        billing_company, vendor_partner_id, invoice_date)

    def _get_customer_billing_bill(self, company, partner_id, origin, date):
        """查询客户账单"""
        return self.env['account.move'].sudo().search([
            ('company_id', '=', company.id),
            ('move_type', '=', 'in_invoice'),
            ('invoice_date', '=', date),
            ('partner_id', '=', partner_id),
            ('invoice_origin', '=', origin),
            ('state', '=', 'draft'),
        ], limit=1)

    def _update_customer_billing_bill(self, billing_company, invoice, mapping, existing_bill, paid_bills=None):
        """更新客户账单（仅处理销售发票的合并账单逻辑，不处理贷项通知单）"""
        invoice_date = invoice.invoice_date
        
        # 处理销售发票的合并账单逻辑
        _logger.info(f"发票 {invoice.id} 状态: {invoice.state}，处理销售发票的合并账单逻辑")
        
        # 获取销售发票
        sales_invoices = self.env['account.move'].sudo().search([
            ('company_id', '=', invoice.company_id.id),
            ('invoice_date', '=', invoice_date),
            ('partner_id', '=', invoice.partner_id.id),
            ('move_type', '=', 'out_invoice'),  # 只查询销售发票
            ('state', '=', 'posted'),
        ])
        
        _logger.info(f"找到 {len(sales_invoices)} 张销售发票，将使用合并逻辑处理")
        
        # 使用映射中的billing_partner_id作为供应商ID
        vendor_partner_id = mapping.billing_partner_id.id
        
        # 扣减已付款账单的金额
        paid_amount_tax_bill = 0
        paid_amount_notax_bill = 0
        
        if paid_bills:
            _logger.info(f"Considering {len(paid_bills)} paid bills in calculation")
            for paid_bill in paid_bills:
                bill_tax_amount = 0
                bill_notax_amount = 0
                for line in paid_bill.invoice_line_ids:
                    if line.tax_ids and any(tax.amount > 0 for tax in line.tax_ids):
                        bill_tax_amount += line.price_total
                        paid_amount_tax_bill += line.price_total
                    else:
                        bill_notax_amount += line.price_total
                        paid_amount_notax_bill += line.price_total
                _logger.info(f"Paid bill {paid_bill.id}: tax_amount={bill_tax_amount}, notax_amount={bill_notax_amount}")
        
        # 计算销售发票的金额（正数）
        sales_amount_tax = 0
        sales_amount_notax = 0
        
        for sales_invoice in sales_invoices:
            for line in sales_invoice.invoice_line_ids:
                if line.tax_ids and any(tax.amount > 0 for tax in line.tax_ids):
                    sales_amount_tax += line.price_total
                else:
                    sales_amount_notax += line.price_total
        
        # 销售发票的净额计算
        total_amount_tax_bill = sales_amount_tax - paid_amount_tax_bill
        total_amount_notax_bill = sales_amount_notax - paid_amount_notax_bill
        
        _logger.info(f"销售发票金额 - 含税: {sales_amount_tax}, 不含税: {sales_amount_notax}")
        
        _logger.info(f"最终合并账单金额 - 含税: {total_amount_tax_bill}, 不含税: {total_amount_notax_bill}")
        
        # 获取产品和账户信息（与创建新账单时相同）
        product_with_tax, expense_account_tax, supplier_taxes = self._get_product_and_accounts(
            billing_company, 'Daily Settlement Products with TAX', 'expense'
        )
        product_without_tax, expense_account_notax, _ = self._get_product_and_accounts(
            billing_company, 'Daily Settlement Products without TAX', 'expense'
        )
        
        # 使用锁机制防止并发创建重复账单
        with self.env.cr.savepoint():
            # 如果存在现有账单，直接更新它
            if existing_bill:
                _logger.info(f"Updating existing Customer Bill: {existing_bill.id}")
                
                # 准备新的账单行
                invoice_line_ids = []
                
                # 只有当含税金额大于0时才添加含税行
                if total_amount_tax_bill > 0:
                    invoice_line_ids.append((0, 0, {
                        'product_id': product_with_tax.id,
                        'quantity': 1.0,
                        'price_unit': total_amount_tax_bill / (1 + sum(tax.amount/100.0 for tax in supplier_taxes)) if supplier_taxes else total_amount_tax_bill,
                        'name': product_with_tax.name,
                        'account_id': expense_account_tax.id,
                        'tax_ids': [(6, 0, supplier_taxes.ids)] if supplier_taxes else []
                    }))
                    _logger.info(f"Adding tax line with amount: {total_amount_tax_bill}")
                
                # 只有当不含税金额大于0时才添加不含税行
                if total_amount_notax_bill > 0:
                    invoice_line_ids.append((0, 0, {
                        'product_id': product_without_tax.id,
                        'quantity': 1.0,
                        'price_unit': total_amount_notax_bill,
                        'name': product_without_tax.name,
                        'account_id': expense_account_notax.id,
                        'tax_ids': []
                    }))
                    _logger.info(f"Adding non-tax line with amount: {total_amount_notax_bill}")
                
                # 如果没有有效的账单行，则删除账单
                if not invoice_line_ids:
                    _logger.info(f"No valid invoice lines, deleting existing bill: {existing_bill.id}")
                    bill_id = existing_bill.id
                    
                    # 根据账单状态采用不同的删除策略
                    if existing_bill.state == 'draft':
                        # Draft 账单：直接删除
                        _logger.info(f"Bill {bill_id} is draft, deleting directly")
                        existing_bill.unlink()
                    else:
                        # Posted 账单：需要先取消过账再删除
                        _logger.info(f"Bill {bill_id} is posted, need to unpost before deletion")
                        
                        # 先取消过账
                        existing_bill.button_draft()
                        _logger.info(f"Bill {bill_id} unposted to draft")
                        
                        # 然后删除
                        existing_bill.unlink()
                        _logger.info(f"Bill {bill_id} deleted after unposting")
                    
                    # 验证账单是否被成功删除
                    deleted_bill = self.env['account.move'].sudo().browse(bill_id)
                    if not deleted_bill.exists():
                        _logger.info(f"Bill {bill_id} successfully deleted")
                    else:
                        _logger.warning(f"Bill {bill_id} still exists after deletion attempt")
                    
                    return
                
                # 检查账单是否已付款
                bill_amount_residual = existing_bill.amount_residual
                bill_amount_total = existing_bill.amount_total
                
                if bill_amount_residual == bill_amount_total:
                    # 未付款账单：直接更新现有账单
                    _logger.info(f"Bill {existing_bill.id} is unpaid (residual: {bill_amount_residual}, total: {bill_amount_total}), updating directly")
                    
                    if existing_bill.state == 'draft':
                        # Draft 账单：直接替换所有行
                        _logger.info(f"Bill {existing_bill.id} is draft, directly replacing lines")
                        existing_bill.write({
                            'invoice_line_ids': [(6, 0, [])] + invoice_line_ids
                        })
                    else:
                        # Posted 账单：需要先取消过账，更新后再重新过账
                        _logger.info(f"Bill {existing_bill.id} is posted, need to unpost first")
                        
                        # 先取消过账
                        existing_bill.button_draft()
                        _logger.info(f"Bill {existing_bill.id} unposted to draft")
                        
                        # 替换账单行
                        existing_bill.write({
                            'invoice_line_ids': [(6, 0, [])] + invoice_line_ids
                        })
                        _logger.info(f"Bill {existing_bill.id} lines updated")
                        
                        # 重新过账
                        existing_bill.action_post()
                        _logger.info(f"Bill {existing_bill.id} reposted")
                else:
                    # 已付款账单：不能修改，需要创建调整账单
                    _logger.info(f"Bill {existing_bill.id} is paid/partially paid (residual: {bill_amount_residual}, total: {bill_amount_total}), creating adjustment bill")
                    
                    # 计算差异金额
                    current_bill_amount = bill_amount_total
                    new_calculated_amount = total_amount_tax_bill + total_amount_notax_bill
                    adjustment_amount = new_calculated_amount - current_bill_amount
                    
                    _logger.info(f"Current bill amount: {current_bill_amount}, new calculated amount: {new_calculated_amount}, adjustment needed: {adjustment_amount}")
                    
                    if abs(adjustment_amount) > 0.01:  # 避免浮点数精度问题
                        # 创建调整账单
                        adjustment_bill = self._create_adjustment_bill(
                            billing_company, mapping, invoice_date, adjustment_amount, 
                            total_amount_tax_bill, total_amount_notax_bill
                        )
                        _logger.info(f"Created adjustment bill: {adjustment_bill.id} with amount: {adjustment_amount}")
                    else:
                        _logger.info(f"No adjustment needed, amounts are equal")
                    
                    return
                _logger.info(f"Updated existing Customer Bill: {existing_bill.id} with {len(invoice_line_ids)} lines")
                return
            
            sales_journal = self.env['account.journal'].sudo().search([
                ('type', '=', 'purchase'),
                ('company_id', '=', billing_company.id)
            ], limit=1)
            
            # 使用映射中的billing_partner_id作为供应商
            vendor_partner_id = mapping.billing_partner_id.id
            
            # 准备账单行，只包含金额大于0的行
            invoice_line_ids = []
            
            # 只有当含税金额大于0时才添加含税行
            if total_amount_tax_bill > 0:
                invoice_line_ids.append((0, 0, {
                    'product_id': product_with_tax.id,
                    'quantity': 1.0,
                    'price_unit': total_amount_tax_bill / (1 + sum(tax.amount/100.0 for tax in supplier_taxes)) if supplier_taxes else total_amount_tax_bill,
                    'name': product_with_tax.name,
                    'account_id': expense_account_tax.id,
                    'tax_ids': [(6, 0, supplier_taxes.ids)] if supplier_taxes else []
                }))
                _logger.info(f"Adding tax line with amount: {total_amount_tax_bill}")
            
            # 只有当不含税金额大于0时才添加不含税行
            if total_amount_notax_bill > 0:
                invoice_line_ids.append((0, 0, {
                    'product_id': product_without_tax.id,
                    'quantity': 1.0,
                    'price_unit': total_amount_notax_bill,
                    'name': product_without_tax.name,
                    'account_id': expense_account_notax.id,
                    'tax_ids': []
                }))
                _logger.info(f"Adding non-tax line with amount: {total_amount_notax_bill}")
            
            # 创建销售发票对应的合并账单（如果有金额）
            if invoice_line_ids:
                bill_vals = {
                    'move_type': 'in_invoice',
                    'partner_id': vendor_partner_id,
                    'company_id': billing_company.id,
                    'journal_id': sales_journal.id,
                    'invoice_date': invoice_date,
                    'invoice_origin': 'Auto Billing',
                    'invoice_line_ids': invoice_line_ids
                }
                
                customer_bill = self.env['account.move'].with_company(billing_company.id).create(bill_vals)
                _logger.info(f"Created merged Customer Bill for sales invoices: {customer_bill.id} with {len(invoice_line_ids)} lines")
                
                # 自动确认新创建的合并账单
                try:
                    customer_bill.action_post()
                    _logger.info(f"Auto-confirmed merged Customer Bill: {customer_bill.id} to posted state")
                except Exception as e:
                    _logger.error(f"Failed to auto-confirm merged Customer Bill {customer_bill.id}: {str(e)}")
                    # 即使自动确认失败，也不影响账单创建

    def _create_credit_note_refund(self, credit_note, credit_tax_amount, credit_notax_amount, 
                               billing_company, vendor_partner_id, invoice_date):
        """为贷项通知单创建对应的退款单"""
        # 获取产品和账户信息
        product_with_tax, expense_account_tax, supplier_taxes = self._get_product_and_accounts(
            billing_company, 'Daily Settlement Products with TAX', 'expense'
        )
        product_without_tax, expense_account_notax, _ = self._get_product_and_accounts(
            billing_company, 'Daily Settlement Products without TAX', 'expense'
        )
        
        # 获取采购日记账
        sales_journal = self.env['account.journal'].sudo().search([
            ('type', '=', 'purchase'),
            ('company_id', '=', billing_company.id)
        ], limit=1)
        
        # 准备贷项通知单的账单行
        credit_bill_lines = []
        
        if credit_tax_amount > 0:
            credit_bill_lines.append((0, 0, {
                'product_id': product_with_tax.id,
                'quantity': 1.0,  # 正数数量，表示减少费用
                'price_unit': credit_tax_amount / (1 + sum(tax.amount/100.0 for tax in supplier_taxes)) if supplier_taxes else credit_tax_amount,
                'name': f"Credit Note - {product_with_tax.name}",
                'account_id': expense_account_tax.id,
                'tax_ids': [(6, 0, supplier_taxes.ids)] if supplier_taxes else []
            }))
        
        if credit_notax_amount > 0:
            credit_bill_lines.append((0, 0, {
                'product_id': product_without_tax.id,
                'quantity': 1.0,  # 正数数量，表示减少费用
                'price_unit': credit_notax_amount,
                'name': f"Credit Note - {product_without_tax.name}",
                'account_id': expense_account_notax.id,
                'tax_ids': []
            }))
        
        if credit_bill_lines:
            # 创建贷项通知单对应的退款单
            credit_bill_vals = {
                'move_type': 'in_refund',  # 门店端对应的是退款单，不是账单
                'partner_id': vendor_partner_id,
                'company_id': billing_company.id,
                'journal_id': sales_journal.id,
                'invoice_date': invoice_date,
                'invoice_origin': 'Auto Billing Credit Note',
                'ref': credit_note.name,  # 设置源文档为贷项通知单号码
                'invoice_line_ids': credit_bill_lines
            }
            
            credit_refund = self.env['account.move'].with_company(billing_company.id).create(credit_bill_vals)
            _logger.info(f"Created Credit Note Refund: {credit_refund.id} for credit note {credit_note.name}")
            
            # 自动确认贷项通知单退款单
            try:
                credit_refund.action_post()
                _logger.info(f"Auto-confirmed Credit Note Refund: {credit_refund.id} to posted state")
            except Exception as e:
                _logger.error(f"Failed to auto-confirm Credit Note Refund {credit_refund.id}: {str(e)}")
                # 即使自动确认失败，也不影响退款单创建
            
            return credit_refund

    def _update_credit_note_refund(self, existing_bill, credit_note, credit_tax_amount, credit_notax_amount):
        """更新贷项通知单对应的退款单（独立于销售发票的合并账单逻辑）"""
        # 获取产品和账户信息
        billing_company = existing_bill.company_id
        product_with_tax, expense_account_tax, supplier_taxes = self._get_product_and_accounts(
            billing_company, 'Daily Settlement Products with TAX', 'expense'
        )
        product_without_tax, expense_account_notax, _ = self._get_product_and_accounts(
            billing_company, 'Daily Settlement Products without TAX', 'expense'
        )
        
        # 准备新的账单行
        credit_bill_lines = []
        
        if credit_tax_amount > 0:
            credit_bill_lines.append((0, 0, {
                'product_id': product_with_tax.id,
                'quantity': 1.0,  # 正数数量，表示减少费用
                'price_unit': credit_tax_amount / (1 + sum(tax.amount/100.0 for tax in supplier_taxes)) if supplier_taxes else credit_tax_amount,
                'name': f"Credit Note - {product_with_tax.name}",
                'account_id': expense_account_tax.id,
                'tax_ids': [(6, 0, supplier_taxes.ids)] if supplier_taxes else []
            }))
        
        if credit_notax_amount > 0:
            credit_bill_lines.append((0, 0, {
                'product_id': product_without_tax.id,
                'quantity': 1.0,  # 正数数量，表示减少费用
                'price_unit': credit_notax_amount,
                'name': f"Credit Note - {product_without_tax.name}",
                'account_id': expense_account_notax.id,
                'tax_ids': []
            }))
        
        if credit_bill_lines:
            # 根据退款单状态采用不同的更新策略
            if existing_bill.state == 'draft':
                # Draft 退款单：直接替换所有行
                _logger.info(f"Credit Note Refund {existing_bill.id} is draft, directly replacing lines")
                existing_bill.write({
                    'invoice_line_ids': [(6, 0, [])] + credit_bill_lines
                })
            else:
                # Posted 退款单：需要先取消过账，更新后再重新过账
                _logger.info(f"Credit Note Refund {existing_bill.id} is posted, need to unpost first")
                
                # 先取消过账
                existing_bill.button_draft()
                _logger.info(f"Credit Note Refund {existing_bill.id} unposted to draft")
                
                # 替换退款单行
                existing_bill.write({
                    'invoice_line_ids': [(6, 0, [])] + credit_bill_lines
                })
                _logger.info(f"Credit Note Refund {existing_bill.id} lines updated")
                
                # 重新过账
                existing_bill.action_post()
                _logger.info(f"Credit Note Refund {existing_bill.id} reposted")
            
            _logger.info(f"Updated Credit Note Refund: {existing_bill.id} for credit note {credit_note.name}")
        else:
            # 如果没有有效行，删除退款单
            _logger.info(f"No valid lines for credit note {credit_note.name}, deleting refund {existing_bill.id}")
            if existing_bill.state == 'posted':
                existing_bill.button_draft()
            existing_bill.unlink()

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
               