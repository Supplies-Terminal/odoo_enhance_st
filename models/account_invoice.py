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
        # 检查是否需要更新客户账单
        move._update_customer_billing()
        return move

    def write(self, vals):
        res = super(AccountInvoice, self).write(vals)
        for record in self:
            if record.operating_company_id:
                record._update_daily_settlement()
            
            # 只处理两个关键事件：reset to draft 和 confirm invoice
            if 'state' in vals:
                if vals['state'] == 'draft':
                    # 发票重置为草稿状态
                    record._handle_draft_invoices_update()
                elif vals['state'] == 'posted':
                    # 发票确认过账
                    record._handle_posted_invoices_update()
        return res

    def unlink(self):
        # 在删除前检查是否需要更新客户账单
        for record in self:
            record._update_customer_billing()
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

    def _update_customer_billing(self):
        """更新客户账单 - 已废弃，保留用于兼容性"""
        _logger.warning("_update_customer_billing 方法已废弃，请使用 _handle_posted_invoices_update")
        pass

    def _handle_posted_invoices_update(self):
        """处理发票确认过账事件"""
        for record in self:
            # 只处理销售发票
            if record.move_type != 'out_invoice':
                continue
            
            # 使用类级别的锁防止重复触发
            lock_key = f"posted_{record.id}_{record.invoice_date}"
            if lock_key in self._billing_update_locks:
                _logger.info(f"跳过重复的过账账单更新: {record.id} {record.name} (锁已存在)")
                continue
            
            # 设置锁
            self._billing_update_locks[lock_key] = True
            
            try:
                _logger.info(f"处理发票过账事件: {record.id} {record.name} {record.invoice_date}")
                
                # 检查是否存在客户账单映射关系
                mapping = self.env['customer.billing.mapping'].search([
                    ('company_id', '=', record.company_id.id),
                    ('partner_id', '=', record.partner_id.id),
                    ('active', '=', True)
                ], limit=1)
                
                if not mapping:
                    continue
                    
                billing_company = mapping.billing_company_id
                invoice_date = record.invoice_date
                
                if not invoice_date:
                    continue
                    
                _logger.info(f"Customer Invoice: {record.id} {record.name} {invoice_date} State: {record.state}")
                _logger.info(f"Billing Company: {billing_company.id} {billing_company.name}")
                
                # 使用映射中的billing_partner_id作为供应商ID
                vendor_partner_id = mapping.billing_partner_id.id
                
                # 检查发票和账单的关系，防止重复生成
                bill_relationship, action = self._check_invoice_bill_relationship(
                    billing_company, vendor_partner_id, invoice_date, record.id
                )
                
                if action == 'cleanup':
                    # 需要清理重复账单
                    _logger.info(f"清理重复账单，然后重新创建")
                    self._force_update_customer_billing_bill(billing_company, record, mapping)
                    continue
                elif action == 'update' and bill_relationship:
                    # 更新现有账单
                    _logger.info(f"更新现有账单 {bill_relationship.id}")
                    self._update_customer_billing_bill(billing_company, record, mapping, bill_relationship)
                    continue
                elif action == 'create':
                    # 创建新账单
                    _logger.info(f"创建新账单")
                    customer_bill = self._get_customer_billing_bill(
                        billing_company, vendor_partner_id, 'Customer Billing', invoice_date
                    )
                    
                    # 如果账单已付款，创建调整单
                    if customer_bill and customer_bill.payment_state == 'paid':
                        self._create_customer_billing_adjustment(billing_company, record, mapping)
                    else:
                        # 更新现有账单或创建新账单
                        self._update_customer_billing_bill(billing_company, record, mapping, customer_bill)
            finally:
                # 清除锁
                if lock_key in self._billing_update_locks:
                    del self._billing_update_locks[lock_key]

    def _handle_draft_invoices_update(self):
        """处理发票重置为草稿状态事件"""
        for record in self:
            # 只处理销售发票
            if record.move_type != 'out_invoice':
                continue
            
            # 使用类级别的锁防止重复触发
            lock_key = f"draft_{record.id}_{record.invoice_date}"
            if lock_key in self._billing_update_locks:
                _logger.info(f"跳过重复的草稿更新: {record.id} {record.name} (锁已存在)")
                continue
            
            # 设置锁
            self._billing_update_locks[lock_key] = True
            
            try:
                _logger.info(f"=== 开始处理发票重置为草稿事件 ===")
                _logger.info(f"发票ID: {record.id}")
                _logger.info(f"发票名称: {record.name}")
                _logger.info(f"发票日期: {record.invoice_date}")
                _logger.info(f"发票状态: {record.state}")
                _logger.info(f"发票金额: {record.amount_total}")
                
                # 检查是否存在客户账单映射关系
                mapping = self.env['customer.billing.mapping'].search([
                    ('company_id', '=', record.company_id.id),
                    ('partner_id', '=', record.partner_id.id),
                    ('active', '=', True)
                ], limit=1)
                
                if mapping and record.invoice_date:
                    _logger.info(f"找到客户账单映射: {mapping.billing_company_id.name} -> {mapping.billing_partner_id.name}")
                    # 强制更新相关账单
                    self._force_update_customer_billing_bill(mapping.billing_company_id, record, mapping)
                    _logger.info(f"完成草稿发票处理: {record.id} {record.name}")
                else:
                    _logger.warning(f"未找到客户账单映射或发票日期为空")
            finally:
                # 清除锁
                if lock_key in self._billing_update_locks:
                    del self._billing_update_locks[lock_key]

    def _force_update_customer_billing_bill(self, billing_company, invoice, mapping):
        """强制更新客户账单，用于处理发票状态变化"""
        invoice_date = invoice.invoice_date
        vendor_partner_id = mapping.billing_partner_id.id
        
        _logger.info(f"Force updating bills for date {invoice_date} and vendor {vendor_partner_id}")
        
        # 使用锁机制防止并发创建重复账单
        with self.env.cr.savepoint():
            # 删除现有的草稿账单
            existing_bills = self.env['account.move'].search([
                ('company_id', '=', billing_company.id),
                ('move_type', '=', 'in_invoice'),
                ('invoice_date', '=', invoice_date),
                ('partner_id', '=', vendor_partner_id),
                ('invoice_origin', '=', 'Customer Billing'),
                ('state', 'in', ['draft', 'posted']),
            ])
            
            _logger.info(f"Found {len(existing_bills)} existing bills to delete")
            
            for bill in existing_bills:
                _logger.info(f"Deleting existing bill due to invoice state change: {bill.id}")
                if bill.state == 'posted':
                    # 如果账单已过账，需要先取消过账
                    for line in bill.line_ids:
                        if line.reconciled:
                            line.remove_move_reconcile()
                    bill.button_draft()
                bill.unlink()
            
            # 最终检查是否还有其他账单（防止重复）
            final_check = self.env['account.move'].search([
                ('company_id', '=', billing_company.id),
                ('move_type', '=', 'in_invoice'),
                ('invoice_date', '=', invoice_date),
                ('partner_id', '=', vendor_partner_id),
                ('invoice_origin', '=', 'Customer Billing'),
                ('state', 'in', ['draft', 'posted']),
            ])
            
            if final_check:
                _logger.error(f"Still found {len(final_check)} bills after deletion, skipping creation to prevent duplicates")
                for bill in final_check:
                    _logger.error(f"Remaining bill: {bill.id} (State: {bill.state})")
                return
            
            # 重新计算并创建账单
            _logger.info(f"Creating new bill after deleting existing ones")
            self._update_customer_billing_bill(billing_company, invoice, mapping, False)
            _logger.info(f"Completed force update for date {invoice_date}")

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

    def _get_customer_billing_bill_for_invoice(self, company, partner_id, origin, date, invoice_id):
        """查询客户账单，并排除指定发票ID"""
        return self.env['account.move'].sudo().search([
            ('company_id', '=', company.id),
            ('move_type', '=', 'in_invoice'),
            ('invoice_date', '=', date),
            ('partner_id', '=', partner_id),
            ('invoice_origin', '=', origin),
            ('state', '=', 'draft'),
            ('id', '!=', invoice_id), # 排除当前发票ID
        ], limit=1)

    def _check_invoice_bill_relationship(self, billing_company, vendor_partner_id, invoice_date, invoice_id):
        """检查发票和账单的关系，防止重复生成"""
        # 查找是否已经为这个发票创建过账单
        existing_bills = self.env['account.move'].search([
            ('company_id', '=', billing_company.id),
            ('move_type', '=', 'in_invoice'),
            ('invoice_date', '=', invoice_date),
            ('partner_id', '=', vendor_partner_id),
            ('invoice_origin', '=', 'Customer Billing'),
            ('state', 'in', ['draft', 'posted']),
        ])
        
        if existing_bills:
            _logger.info(f"日期 {invoice_date} 已存在 {len(existing_bills)} 个账单")
            for bill in existing_bills:
                _logger.info(f"  - 账单 {bill.id} (状态: {bill.state})")
            
            # 如果存在账单，检查是否需要更新而不是创建新的
            if len(existing_bills) == 1:
                existing_bill = existing_bills[0]
                _logger.info(f"找到现有账单 {existing_bill.id}，将更新而不是创建新的")
                return existing_bill, 'update'
            else:
                _logger.warning(f"发现多个账单，需要清理重复")
                return None, 'cleanup'
        
        return None, 'create'

    def _update_customer_billing_bill(self, billing_company, invoice, mapping, existing_bill):
        """更新客户账单"""
        invoice_date = invoice.invoice_date
        
        # 获取所有相关的发票行，包括所有状态
        all_invoices = self.env['account.move'].search([
            ('company_id', '=', invoice.company_id.id),
            ('invoice_date', '=', invoice_date),
            ('partner_id', '=', invoice.partner_id.id),
            ('move_type', '=', 'out_invoice'),
        ])
        
        # 根据当前发票状态决定计算逻辑
        if invoice.state == 'draft':
            # 如果当前发票是草稿状态，考虑所有状态的发票（包括草稿）
            _logger.info(f"发票 {invoice.id} 是草稿状态，计算所有状态的发票金额")
            relevant_invoices = all_invoices
        else:
            # 如果当前发票是已过账状态，只计算已过账发票的金额
            _logger.info(f"发票 {invoice.id} 是已过账状态，只计算已过账发票的金额")
            relevant_invoices = all_invoices.filtered(lambda inv: inv.state == 'posted')
        
        all_invoice_lines = relevant_invoices.mapped('invoice_line_ids')
        
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
        
        _logger.info(f"计算得到含税金额: {total_amount_tax}, 不含税金额: {total_amount_notax}")
        
        # 使用映射中的billing_partner_id作为供应商ID
        vendor_partner_id = mapping.billing_partner_id.id
        
        # 扣减已过账的账单部分
        posted_bills = self.env['account.move'].search([
            ('company_id', '=', billing_company.id),
            ('move_type', '=', 'in_invoice'),
            ('invoice_date', '=', invoice_date),
            ('partner_id', '=', vendor_partner_id),
            ('invoice_origin', '=', 'Customer Billing'),
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
        
        _logger.info(f"最终账单金额 - 含税: {total_amount_tax_bill}, 不含税: {total_amount_notax_bill}")
        
        # 使用锁机制防止并发创建重复账单
        with self.env.cr.savepoint():
            # 再次检查是否已存在账单（防止并发问题）
            current_bills = self.env['account.move'].search([
                ('company_id', '=', billing_company.id),
                ('move_type', '=', 'in_invoice'),
                ('invoice_date', '=', invoice_date),
                ('partner_id', '=', vendor_partner_id),
                ('invoice_origin', '=', 'Customer Billing'),
                ('state', 'in', ['draft', 'posted']),
            ])
            
            if current_bills:
                _logger.info(f"Found {len(current_bills)} existing bills, deleting them to prevent duplicates")
                for bill in current_bills:
                    _logger.info(f"Deleting existing bill: {bill.id} (State: {bill.state})")
                    if bill.state == 'posted':
                        # 如果账单已过账，需要先取消过账
                        for line in bill.line_ids:
                            if line.reconciled:
                                line.remove_move_reconcile()
                        bill.button_draft()
                    bill.unlink()
            
            # 如果存在草稿状态的账单，先删除
            if existing_bill:
                _logger.info(f"Deleting existing Customer Bill: {existing_bill.id}")
                for line in existing_bill.line_ids:
                    if line.reconciled:
                        line.remove_move_reconcile()
                if existing_bill.name != '/':
                    existing_bill.name = '/'
                existing_bill.button_draft()
                existing_bill.unlink()
            
            # 最终检查是否还有其他账单（防止重复）
            final_check = self.env['account.move'].search([
                ('company_id', '=', billing_company.id),
                ('move_type', '=', 'in_invoice'),
                ('invoice_date', '=', invoice_date),
                ('partner_id', '=', vendor_partner_id),
                ('invoice_origin', '=', 'Customer Billing'),
                ('state', 'in', ['draft', 'posted']),
            ])
            
            if final_check:
                _logger.error(f"Still found {len(final_check)} bills after deletion, skipping creation to prevent duplicates")
                for bill in final_check:
                    _logger.error(f"Remaining bill: {bill.id} (State: {bill.state})")
                return
            
            # 创建新账单
            _logger.info("Creating new Customer Bill")
            product_with_tax, expense_account_tax, supplier_taxes = self._get_product_and_accounts(
                billing_company, 'Daily Settlement Products with TAX', 'expense'
            )
            product_without_tax, expense_account_notax, _ = self._get_product_and_accounts(
                billing_company, 'Daily Settlement Products without TAX', 'expense'
            )
            
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
            
            # 如果没有有效的账单行，则不创建账单
            if not invoice_line_ids:
                _logger.info(f"No valid invoice lines to create bill for date {invoice_date}, skipping bill creation")
                return
            
            bill_vals = {
                'move_type': 'in_invoice',
                'partner_id': vendor_partner_id,
                'company_id': billing_company.id,
                'journal_id': sales_journal.id,
                'invoice_date': invoice_date,
                'invoice_origin': 'Customer Billing',
                'invoice_line_ids': invoice_line_ids
            }
            
            customer_bill = self.env['account.move'].with_company(billing_company.id).create(bill_vals)
            _logger.info(f"Created Customer Bill: {customer_bill.id} with {len(invoice_line_ids)} lines")

    def _check_and_prevent_duplicate_bills(self, billing_company, vendor_partner_id, invoice_date):
        """检查并防止重复账单的辅助方法"""
        # 检查是否已存在相同条件的账单
        existing_bills = self.env['account.move'].search([
            ('company_id', '=', billing_company.id),
            ('move_type', '=', 'in_invoice'),
            ('invoice_date', '=', invoice_date),
            ('partner_id', '=', vendor_partner_id),
            ('invoice_origin', '=', 'Customer Billing'),
            ('state', 'in', ['draft', 'posted']),
        ])
        
        if existing_bills:
            _logger.warning(f"Found {len(existing_bills)} existing bills for {invoice_date}, preventing duplicate creation")
            for bill in existing_bills:
                _logger.warning(f"Existing bill: {bill.id} (State: {bill.state})")
            return True  # 表示存在重复
        
        return False  # 表示不存在重复

    def _cleanup_duplicate_bills(self, billing_company, vendor_partner_id, invoice_date):
        """清理重复账单的辅助方法"""
        duplicate_bills = self.env['account.move'].search([
            ('company_id', '=', billing_company.id),
            ('move_type', '=', 'in_invoice'),
            ('invoice_date', '=', invoice_date),
            ('partner_id', '=', vendor_partner_id),
            ('invoice_origin', '=', 'Customer Billing'),
            ('state', 'in', ['draft', 'posted']),
        ])
        
        if len(duplicate_bills) > 1:
            _logger.warning(f"Found {len(duplicate_bills)} duplicate bills, keeping only the first one")
            # 保留第一个，删除其余的
            bills_to_delete = duplicate_bills[1:]
            for bill in bills_to_delete:
                _logger.info(f"Deleting duplicate bill: {bill.id}")
                if bill.state == 'posted':
                    for line in bill.line_ids:
                        if line.reconciled:
                            line.remove_move_reconcile()
                    bill.button_draft()
                bill.unlink()
            return True
        
        return False

    @api.model
    def cleanup_billing_locks(self):
        """清理过期的账单更新锁"""
        current_time = fields.Datetime.now()
        if not hasattr(self, '_billing_update_locks'):
            return
        
        # 清理超过1小时的锁
        locks_to_remove = []
        for lock_key in self._billing_update_locks.keys():
            # 这里可以添加时间戳检查逻辑
            # 暂时简单清理所有锁
            locks_to_remove.append(lock_key)
        
        for lock_key in locks_to_remove:
            del self._billing_update_locks[lock_key]
        
        _logger.info(f"清理了 {len(locks_to_remove)} 个账单更新锁")

    @api.model
    def get_billing_locks_status(self):
        """获取当前账单更新锁的状态"""
        if not hasattr(self, '_billing_update_locks'):
            return "未初始化"
        
        lock_count = len(self._billing_update_locks)
        lock_keys = list(self._billing_update_locks.keys())
        
        return {
            'lock_count': lock_count,
            'lock_keys': lock_keys
        }

    def _create_customer_billing_adjustment(self, billing_company, invoice, mapping):
        """创建客户账单调整单"""
        invoice_date = invoice.invoice_date
        
        # 获取所有相关的发票行，包括所有状态
        all_invoices = self.env['account.move'].search([
            ('company_id', '=', invoice.company_id.id),
            ('invoice_date', '=', invoice_date),
            ('partner_id', '=', invoice.partner_id.id),
            ('move_type', '=', 'out_invoice'),
        ])
        
        # 只计算已过账发票的金额
        posted_invoices = all_invoices.filtered(lambda inv: inv.state == 'posted')
        all_invoice_lines = posted_invoices.mapped('invoice_line_ids')
        
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
        
        # 使用映射中的billing_partner_id作为供应商ID
        vendor_partner_id = mapping.billing_partner_id.id
        
        # 获取已过账的账单总额
        posted_bills = self.env['account.move'].search([
            ('company_id', '=', billing_company.id),
            ('move_type', '=', 'in_invoice'),
            ('invoice_date', '=', invoice_date),
            ('partner_id', '=', vendor_partner_id),
            ('invoice_origin', '=', 'Customer Billing'),
            ('state', '=', 'posted'),
        ])
        
        posted_amount_tax_bill = sum(
            line.price_unit for bill in posted_bills for line in bill.invoice_line_ids if line.tax_ids
        )
        posted_amount_notax_bill = sum(
            line.price_unit for bill in posted_bills for line in bill.invoice_line_ids if not line.tax_ids
        )
        
        # 计算调整金额
        adjustment_tax = total_amount_tax - posted_amount_tax_bill
        adjustment_notax = total_amount_notax - posted_amount_notax_bill
        
        # 创建调整单
        if adjustment_tax != 0 or adjustment_notax != 0:
            _logger.info("Creating Customer Billing Adjustment")
            product_with_tax, expense_account_tax, supplier_taxes = self._get_product_and_accounts(
                billing_company, 'Daily Settlement Products with TAX', 'expense'
            )
            product_without_tax, expense_account_notax, _ = self._get_product_and_accounts(
                billing_company, 'Daily Settlement Products without TAX', 'expense'
            )
            
            sales_journal = self.env['account.journal'].sudo().search([
                ('type', '=', 'purchase'),
                ('company_id', '=', billing_company.id)
            ], limit=1)
            
            # 使用映射中的billing_partner_id作为供应商
            vendor_partner_id = mapping.billing_partner_id.id
            
            adjustment_vals = {
                'move_type': 'in_invoice',
                'partner_id': vendor_partner_id,
                'company_id': billing_company.id,
                'journal_id': sales_journal.id,
                'invoice_date': invoice_date,
                'invoice_origin': 'Customer Billing Adjustment',
                'invoice_line_ids': []
            }
            
            if adjustment_tax != 0:
                adjustment_vals['invoice_line_ids'].append((0, 0, {
                    'product_id': product_with_tax.id,
                    'quantity': 1.0,
                    'price_unit': adjustment_tax / (1 + sum(tax.amount/100.0 for tax in supplier_taxes)) if supplier_taxes else adjustment_tax,
                    'name': f"{product_with_tax.name} - Adjustment",
                    'account_id': expense_account_tax.id,
                    'tax_ids': [(6, 0, supplier_taxes.ids)] if supplier_taxes else []
                }))
            
            if adjustment_notax != 0:
                adjustment_vals['invoice_line_ids'].append((0, 0, {
                    'product_id': product_without_tax.id,
                    'quantity': 1.0,
                    'price_unit': adjustment_notax,
                    'name': f"{product_without_tax.name} - Adjustment",
                    'account_id': expense_account_notax.id,
                    'tax_ids': []
                }))
            
            adjustment_bill = self.env['account.move'].with_company(billing_company.id).create(adjustment_vals)
            _logger.info(f"Created Customer Billing Adjustment: {adjustment_bill.id}")
                
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
               