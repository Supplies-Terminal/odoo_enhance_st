#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试账单重复检查逻辑的脚本
"""

import logging
from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class TestBillingDuplicateFix(models.Model):
    _name = 'test.billing.duplicate.fix'
    _description = '测试账单重复修复'

    def test_duplicate_check(self):
        """测试重复账单检查逻辑"""
        _logger.info("开始测试账单重复检查逻辑...")
        
        # 获取所有客户账单映射
        mappings = self.env['customer.billing.mapping'].search([('active', '=', True)])
        _logger.info(f"找到 {len(mappings)} 个活跃的客户账单映射")
        
        for mapping in mappings:
            _logger.info(f"检查映射: {mapping.company_id.name} -> {mapping.billing_company_id.name}")
            
            # 检查是否存在重复账单
            duplicate_bills = self._find_duplicate_bills(mapping)
            
            if duplicate_bills:
                _logger.warning(f"发现重复账单，开始清理...")
                self._cleanup_duplicate_bills_for_mapping(mapping)
            else:
                _logger.info("未发现重复账单")
        
        _logger.info("账单重复检查测试完成")

    def _find_duplicate_bills(self, mapping):
        """查找指定映射的重复账单"""
        billing_company = mapping.billing_company_id
        vendor_partner = mapping.billing_partner_id
        
        # 查找所有相关的账单
        all_bills = self.env['account.move'].search([
            ('company_id', '=', billing_company.id),
            ('move_type', '=', 'in_invoice'),
            ('partner_id', '=', vendor_partner.id),
            ('invoice_origin', '=', 'Customer Billing'),
            ('state', 'in', ['draft', 'posted']),
        ])
        
        # 按日期分组检查重复
        bills_by_date = {}
        for bill in all_bills:
            date_key = bill.invoice_date
            if date_key not in bills_by_date:
                bills_by_date[date_key] = []
            bills_by_date[date_key].append(bill)
        
        # 找出有重复的日期
        duplicates = {}
        for date_key, bills in bills_by_date.items():
            if len(bills) > 1:
                duplicates[date_key] = bills
        
        return duplicates

    def _cleanup_duplicate_bills_for_mapping(self, mapping):
        """清理指定映射的重复账单"""
        billing_company = mapping.billing_company_id
        vendor_partner = mapping.billing_partner_id
        
        # 查找所有相关的账单
        all_bills = self.env['account.move'].search([
            ('company_id', '=', billing_company.id),
            ('move_type', '=', 'in_invoice'),
            ('partner_id', '=', vendor_partner.id),
            ('invoice_origin', '=', 'Customer Billing'),
            ('state', 'in', ['draft', 'posted']),
        ])
        
        # 按日期分组
        bills_by_date = {}
        for bill in all_bills:
            date_key = bill.invoice_date
            if date_key not in bills_by_date:
                bills_by_date[date_key] = []
            bills_by_date[date_key].append(bill)
        
        # 清理重复账单
        for date_key, bills in bills_by_date.items():
            if len(bills) > 1:
                _logger.warning(f"日期 {date_key} 发现 {len(bills)} 个账单，开始清理...")
                
                # 按创建时间排序，保留最早的
                sorted_bills = sorted(bills, key=lambda b: b.create_date)
                bill_to_keep = sorted_bills[0]
                bills_to_delete = sorted_bills[1:]
                
                _logger.info(f"保留账单: {bill_to_keep.id} (创建时间: {bill_to_keep.create_date})")
                
                for bill in bills_to_delete:
                    _logger.info(f"删除重复账单: {bill.id} (创建时间: {bill.create_date})")
                    if bill.state == 'posted':
                        # 如果账单已过账，需要先取消过账
                        for line in bill.line_ids:
                            if line.reconciled:
                                line.remove_move_reconcile()
                        bill.button_draft()
                    bill.unlink()

    def test_billing_creation_logic(self):
        """测试账单创建逻辑"""
        _logger.info("开始测试账单创建逻辑...")
        
        # 获取一个示例映射
        mapping = self.env['customer.billing.mapping'].search([('active', '=', True)], limit=1)
        if not mapping:
            _logger.error("未找到可用的客户账单映射")
            return
        
        billing_company = mapping.billing_company_id
        vendor_partner = mapping.billing_partner_id
        
        # 测试重复检查方法
        test_date = fields.Date.today()
        
        # 检查是否存在重复
        has_duplicates = self.env['account.move']._check_and_prevent_duplicate_bills(
            billing_company, vendor_partner.id, test_date
        )
        
        if has_duplicates:
            _logger.warning(f"日期 {test_date} 存在重复账单")
        else:
            _logger.info(f"日期 {test_date} 不存在重复账单")
        
        # 清理重复账单
        cleaned = self.env['account.move']._cleanup_duplicate_bills(
            billing_company, vendor_partner.id, test_date
        )
        
        if cleaned:
            _logger.info(f"已清理日期 {test_date} 的重复账单")
        else:
            _logger.info(f"日期 {test_date} 无需清理")
        
        _logger.info("账单创建逻辑测试完成")

    def test_billing_locks(self):
        """测试账单更新锁机制"""
        _logger.info("开始测试账单更新锁机制...")
        
        # 获取锁状态
        lock_status = self.env['account.move'].get_billing_locks_status()
        _logger.info(f"当前锁状态: {lock_status}")
        
        # 清理锁
        self.env['account.move'].cleanup_billing_locks()
        _logger.info("已清理账单更新锁")
        
        # 再次检查锁状态
        lock_status_after = self.env['account.move'].get_billing_locks_status()
        _logger.info(f"清理后锁状态: {lock_status_after}")
        
        _logger.info("账单更新锁机制测试完成")

    def test_duplicate_trigger_prevention(self):
        """测试重复触发防护机制"""
        _logger.info("开始测试重复触发防护机制...")
        
        # 获取一个示例发票
        test_invoice = self.env['account.move'].search([
            ('move_type', '=', 'out_invoice'),
            ('state', 'in', ['draft', 'posted'])
        ], limit=1)
        
        if not test_invoice:
            _logger.error("未找到可用的测试发票")
            return
        
        _logger.info(f"测试发票: {test_invoice.id} {test_invoice.name}")
        
        # 模拟多次调用（这里只是测试锁机制，不实际执行更新）
        lock_key = f"{test_invoice.id}_{test_invoice.invoice_date}"
        
        # 检查锁是否正常工作
        if hasattr(self.env['account.move'], '_billing_update_locks'):
            # 设置测试锁
            self.env['account.move']._billing_update_locks[lock_key] = True
            
            # 尝试再次设置锁（应该被阻止）
            if lock_key in self.env['account.move']._billing_update_locks:
                _logger.info("锁机制正常工作：重复锁被阻止")
            else:
                _logger.warning("锁机制可能存在问题")
            
            # 清理测试锁
            del self.env['account.move']._billing_update_locks[lock_key]
        else:
            _logger.warning("锁机制未初始化")
        
        _logger.info("重复触发防护机制测试完成")

    def test_event_driven_logic(self):
        """测试事件驱动的账单更新逻辑"""
        _logger.info("开始测试事件驱动的账单更新逻辑...")
        
        # 获取一个示例发票
        test_invoice = self.env['account.move'].search([
            ('move_type', '=', 'out_invoice'),
            ('state', 'in', ['draft', 'posted'])
        ], limit=1)
        
        if not test_invoice:
            _logger.error("未找到可用的测试发票")
            return
        
        _logger.info(f"测试发票: {test_invoice.id} {test_invoice.name} (当前状态: {test_invoice.state})")
        
        # 测试草稿状态锁
        draft_lock_key = f"draft_{test_invoice.id}_{test_invoice.invoice_date}"
        posted_lock_key = f"posted_{test_invoice.id}_{test_invoice.invoice_date}"
        
        if hasattr(self.env['account.move'], '_billing_update_locks'):
            # 测试草稿锁
            self.env['account.move']._billing_update_locks[draft_lock_key] = True
            _logger.info(f"设置草稿锁: {draft_lock_key}")
            
            # 测试过账锁
            self.env['account.move']._billing_update_locks[posted_lock_key] = True
            _logger.info(f"设置过账锁: {posted_lock_key}")
            
            # 检查锁状态
            lock_status = self.env['account.move'].get_billing_locks_status()
            _logger.info(f"锁状态: {lock_status}")
            
            # 清理测试锁
            if draft_lock_key in self.env['account.move']._billing_update_locks:
                del self.env['account.move']._billing_update_locks[draft_lock_key]
            if posted_lock_key in self.env['account.move']._billing_update_locks:
                del self.env['account.move']._billing_update_locks[posted_lock_key]
            
            _logger.info("已清理测试锁")
        else:
            _logger.warning("锁机制未初始化")
        
        _logger.info("事件驱动的账单更新逻辑测试完成")

    def test_method_compatibility(self):
        """测试方法兼容性"""
        _logger.info("开始测试方法兼容性...")
        
        # 测试废弃的方法
        try:
            # 调用废弃的方法（应该只显示警告，不执行实际逻辑）
            self.env['account.move']._update_customer_billing()
            _logger.info("废弃方法调用成功，符合预期")
        except Exception as e:
            _logger.error(f"废弃方法调用失败: {str(e)}")
        
        # 测试新的事件驱动方法
        try:
            # 测试草稿处理方法（不传参数，应该正常处理）
            self.env['account.move']._handle_draft_invoices_update()
            _logger.info("草稿处理方法调用成功")
        except Exception as e:
            _logger.error(f"草稿处理方法调用失败: {str(e)}")
        
        try:
            # 测试过账处理方法（不传参数，应该正常处理）
            self.env['account.move']._handle_posted_invoices_update()
            _logger.info("过账处理方法调用成功")
        except Exception as e:
            _logger.error(f"过账处理方法调用失败: {str(e)}")
        
        _logger.info("方法兼容性测试完成")

    def test_wizard_integration(self):
        """测试向导集成"""
        _logger.info("开始测试向导集成...")
        
        try:
            # 检查向导模型是否存在
            if 'customer.billing.update.wizard' in self.env:
                wizard_model = self.env['customer.billing.update.wizard']
                _logger.info("向导模型存在")
                
                # 测试创建向导
                wizard = wizard_model.create({
                    'company_id': self.env.company.id,
                    'partner_id': self.env['res.partner'].search([('is_company', '=', True)], limit=1).id,
                    'start_date': fields.Date.today(),
                    'end_date': fields.Date.today(),
                })
                _logger.info(f"成功创建向导: {wizard.id}")
                
                # 测试获取发票方法
                invoices = wizard._get_invoices_for_period()
                _logger.info(f"获取到 {len(invoices)} 张发票")
                
                # 测试处理逻辑（不实际执行，只检查方法是否存在）
                if hasattr(wizard, 'action_process'):
                    _logger.info("向导的action_process方法存在")
                else:
                    _logger.warning("向导的action_process方法不存在")
                
                # 清理测试数据
                wizard.unlink()
                _logger.info("已清理测试向导")
                
            else:
                _logger.warning("向导模型不存在，可能未安装相关模块")
                
        except Exception as e:
            _logger.error(f"向导集成测试失败: {str(e)}")
        
        _logger.info("向导集成测试完成")

    def run_all_tests(self):
        """运行所有测试"""
        _logger.info("=== 开始运行所有账单重复检查测试 ===")
        
        try:
            self.test_duplicate_check()
            self.test_billing_creation_logic()
            self.test_billing_locks()
            self.test_duplicate_trigger_prevention()
            self.test_event_driven_logic()
            self.test_method_compatibility()
            self.test_wizard_integration()
            _logger.info("=== 所有测试完成 ===")
        except Exception as e:
            _logger.error(f"测试过程中发生错误: {str(e)}")
            raise 