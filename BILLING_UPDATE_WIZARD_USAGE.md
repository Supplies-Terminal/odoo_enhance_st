# 客户账单更新向导使用说明

## 功能概述

客户账单更新向导（Customer Billing Update Wizard）是一个强大的工具，允许您手动触发历史订单的账单更新逻辑，为指定期间内的发票生成或更新对应的账单。

## 主要特性

### 1. **灵活的日期选择**
- **月度更新**：自动选择当前月份的第一天和最后一天
- **日期范围**：自定义开始和结束日期
- **特定月份**：选择具体的月份（如2024年1月）

### 2. **智能配置**
- 自动创建客户账单映射关系（如果不存在）
- 动态更新供应商选择域
- 日期范围验证（不超过12个月）

### 3. **安全处理**
- **预览模式**：先查看将要处理的数据，不进行实际更改
- **实际处理**：执行真正的账单更新操作
- 详细的处理日志和错误处理

### 4. **完整报告**
- 处理前预览摘要
- 处理后结果摘要
- 按日期分组的发票统计

## 使用方法

### 1. **访问向导**
```
Accounting → Configuration → Billing Update Wizard
```

### 2. **配置参数**

#### 公司配置
- **Sales Company**：选择发票所属的公司（如：syntac）
- **Customer**：选择需要生成账单的客户（如：jo's tea）

#### 账单配置
- **Billing Company**：选择生成账单的目标公司（如：jo's tea公司）
- **Billing Vendor**：选择账单公司下的供应商（如：jo's tea公司下的"syntac"客户）

#### 更新配置
- **Update Type**：选择更新类型
  - Monthly Update：当前月份
  - Date Range Update：自定义日期范围
  - Specific Month：特定月份
- **Start Date**：开始日期（自动设置）
- **End Date**：结束日期（自动设置）
- **Specific Month**：特定月份（当选择Specific Month时显示）

#### 处理选项
- **Force Recreate Bills**：强制重新创建账单（删除现有账单）
- **Dry Run (Preview Only)**：预览模式（默认启用）

### 3. **执行流程**

#### 步骤1：预览（推荐）
1. 配置所有必要参数
2. 确保 "Dry Run" 已勾选
3. 点击 **Preview** 按钮
4. 查看处理摘要，确认数据正确

#### 步骤2：实际处理
1. 取消勾选 "Dry Run"
2. 点击 **Process** 按钮
3. 等待处理完成
4. 查看结果摘要

## 使用场景示例

### 场景1：处理上个月的发票
```
Update Type: Specific Month
Specific Month: 2024-01-01 (自动设置为1月1日到1月31日)
```

### 场景2：处理特定日期范围
```
Update Type: Date Range Update
Start Date: 2024-01-15
End Date: 2024-02-15
```

### 场景3：处理当前月份
```
Update Type: Monthly Update
(自动使用当前月份)
```

## 技术细节

### 1. **映射关系管理**
- 如果映射关系不存在，向导会自动创建
- 确保数据的一致性和完整性

### 2. **发票处理逻辑**
- 按日期分组处理发票
- 调用现有的 `_update_customer_billing()` 方法
- 支持所有状态的发票（草稿、已过账等）

### 3. **错误处理**
- 详细的日志记录
- 单个发票处理失败不影响其他发票
- 用户友好的错误消息

### 4. **性能优化**
- 批量处理发票
- 智能的数据库查询
- 内存使用优化

## 注意事项

### 1. **数据安全**
- 始终先使用预览模式
- 确认数据正确后再执行实际处理
- 建议在测试环境中先验证

### 2. **系统资源**
- 处理大量历史数据时可能需要较长时间
- 建议在系统负载较低时执行
- 监控系统性能和内存使用

### 3. **权限要求**
- 需要 `account.group_account_user` 权限
- 确保有足够的权限访问相关公司和合作伙伴

### 4. **数据一致性**
- 向导会验证所有必要的配置
- 自动处理映射关系的创建
- 确保账单数据的准确性

## 故障排除

### 常见问题

#### 1. **没有找到发票**
- 检查日期范围是否正确
- 确认公司和客户选择是否正确
- 验证发票是否存在于指定期间

#### 2. **处理失败**
- 查看系统日志获取详细错误信息
- 检查产品配置是否正确
- 确认日记账和科目设置

#### 3. **权限错误**
- 确认用户有正确的权限组
- 检查公司访问权限
- 验证合作伙伴访问权限

### 日志查看
- 所有操作都会记录在系统日志中
- 使用日志级别 INFO 查看详细信息
- 错误信息会显示在用户界面中

## 最佳实践

### 1. **定期维护**
- 每月使用向导处理历史数据
- 及时处理发票状态变化
- 保持账单数据的同步

### 2. **数据验证**
- 处理前后对比发票和账单数据
- 验证金额计算的准确性
- 检查税务处理的正确性

### 3. **性能优化**
- 分批处理大量数据
- 选择合适的处理时间
- 监控系统资源使用

## 总结

客户账单更新向导是一个强大的工具，能够帮助您：
- 处理历史发票的账单生成
- 维护数据的一致性和准确性
- 自动化复杂的账单更新流程
- 提供完整的处理报告和日志

通过合理使用这个向导，您可以确保客户账单系统始终保持最新和准确的状态。

# 账单重复问题解决方案

## 问题描述

在客户账单生成过程中，有时会出现重复账单的问题，主要原因包括：

1. **并发处理问题**：多个发票同时触发账单更新时，可能创建重复账单
2. **状态检查不够严格**：只检查草稿状态，没有检查已过账的账单
3. **删除逻辑不够彻底**：可能存在竞态条件
4. **重复触发问题**：同一发票的 `write` 方法被多次调用，导致多次账单更新

## 解决方案

### 1. 增强的重复检查逻辑

在 `_update_customer_billing_bill` 方法中添加了多层重复检查：

```python
# 使用锁机制防止并发创建重复账单
with self.env.cr.savepoint():
    # 再次检查是否已存在账单（防止并发问题）
    current_bills = self.env['account.move'].search([
        ('company_id', '=', billing_company.id),
        ('move_type', '=', 'in_invoice'),
        ('invoice_date', '=', invoice_date),
        ('partner_id', '=', vendor_partner_id),
        ('invoice_origin', '=', 'Customer Billing'),
        ('state', 'in', ['draft', 'posted']),  # 检查所有状态
    ])
    
    if current_bills:
        # 删除所有现有账单
        for bill in current_bills:
            if bill.state == 'posted':
                # 处理已过账账单
                for line in bill.line_ids:
                    if line.reconciled:
                        line.remove_move_reconcile()
                bill.button_draft()
            bill.unlink()
    
    # 最终检查
    final_check = self.env['account.move'].search([...])
    if final_check:
        _logger.error("仍然存在账单，跳过创建以防止重复")
        return
```

### 2. 事务保护

使用 `savepoint` 确保操作的原子性：

```python
with self.env.cr.savepoint():
    # 所有操作在一个事务中执行
    # 如果出现错误，可以回滚到保存点
```

### 3. 防重复触发机制 ⭐ **新增**

#### 类级别锁机制

为了防止同一发票的多次触发，添加了类级别的锁机制：

```python
class AccountInvoice(models.Model):
    _inherit = 'account.move'
    
    # 类级别的防重复锁
    _billing_update_locks = {}
    
    def _update_customer_billing(self):
        for record in self:
            # 使用类级别的锁防止重复触发
            lock_key = f"{record.id}_{record.invoice_date}"
            if lock_key in self._billing_update_locks:
                _logger.info(f"跳过重复的账单更新: {record.id} {record.name} (锁已存在)")
                continue
            
            # 设置锁
            self._billing_update_locks[lock_key] = True
            
            try:
                # 执行账单更新逻辑
                pass
            finally:
                # 清除锁
                if lock_key in self._billing_update_locks:
                    del self._billing_update_locks[lock_key]
```

#### 锁管理方法

```python
@api.model
def cleanup_billing_locks(self):
    """清理过期的账单更新锁"""
    # 清理所有锁，防止内存泄漏
    
@api.model
def get_billing_locks_status(self):
    """获取当前账单更新锁的状态"""
    # 返回当前锁的数量和键值
```

### 4. 新增的辅助方法

#### `_check_and_prevent_duplicate_bills`

检查指定日期和供应商是否已存在账单：

```python
def _check_and_prevent_duplicate_bills(self, billing_company, vendor_partner_id, invoice_date):
    """检查并防止重复账单的辅助方法"""
    existing_bills = self.env['account.move'].search([
        ('company_id', '=', billing_company.id),
        ('move_type', '=', 'in_invoice'),
        ('invoice_date', '=', invoice_date),
        ('partner_id', '=', vendor_partner_id),
        ('invoice_origin', '=', 'Customer Billing'),
        ('state', 'in', ['draft', 'posted']),
    ])
    
    if existing_bills:
        _logger.warning(f"发现重复账单，阻止创建")
        return True
    
    return False
```

#### `_cleanup_duplicate_bills`

清理已存在的重复账单：

```python
def _cleanup_duplicate_bills(self, billing_company, vendor_partner_id, invoice_date):
    """清理重复账单的辅助方法"""
    duplicate_bills = self.env['account.move'].search([...])
    
    if len(duplicate_bills) > 1:
        # 保留第一个，删除其余的
        bills_to_delete = duplicate_bills[1:]
        for bill in bills_to_delete:
            if bill.state == 'posted':
                # 处理已过账账单
                for line in bill.line_ids:
                    if line.reconciled:
                        line.remove_move_reconcile()
                bill.button_draft()
            bill.unlink()
        return True
    
    return False
```

### 5. 测试脚本

创建了 `test_billing_duplicate_fix.py` 测试脚本，包含：

- `test_duplicate_check()`: 检查所有映射的重复账单
- `test_billing_creation_logic()`: 测试账单创建逻辑
- `test_billing_locks()`: 测试账单更新锁机制 ⭐ **新增**
- `test_duplicate_trigger_prevention()`: 测试重复触发防护机制 ⭐ **新增**
- `_find_duplicate_bills()`: 查找重复账单
- `_cleanup_duplicate_bills_for_mapping()`: 清理指定映射的重复账单

## 使用方法

### 1. 运行测试

```python
# 在Odoo shell中运行
test_model = env['test.billing.duplicate.fix']
test_model.run_all_tests()
```

### 2. 手动清理重复账单

```python
# 清理特定映射的重复账单
mapping = env['customer.billing.mapping'].search([('id', '=', mapping_id)])
test_model = env['test.billing.duplicate.fix']
test_model._cleanup_duplicate_bills_for_mapping(mapping)
```

### 3. 检查特定日期的重复

```python
# 检查特定日期的重复账单
billing_company = env['res.company'].search([('id', '=', company_id)])
vendor_partner = env['res.partner'].search([('id', '=', partner_id)])
invoice_date = fields.Date.today()

has_duplicates = env['account.move']._check_and_prevent_duplicate_bills(
    billing_company, vendor_partner.id, invoice_date
)
```

### 4. 管理账单更新锁 ⭐ **新增**

```python
# 查看当前锁状态
lock_status = env['account.move'].get_billing_locks_status()
print(f"当前锁数量: {lock_status['lock_count']}")

# 清理所有锁
env['account.move'].cleanup_billing_locks()

# 再次检查锁状态
lock_status_after = env['account.move'].get_billing_locks_status()
print(f"清理后锁数量: {lock_status_after['lock_count']}")
```

## 改进效果

1. **防止并发重复**：使用事务锁和保存点机制
2. **防止重复触发**：使用类级别锁机制 ⭐ **新增**
3. **全面状态检查**：检查草稿和已过账状态
4. **多层验证**：创建前多次检查，确保无重复
5. **详细日志**：记录所有操作，便于调试
6. **自动清理**：提供自动清理重复账单的方法
7. **锁管理**：防止内存泄漏和锁状态监控 ⭐ **新增**

## 注意事项

1. **性能影响**：增加了额外的数据库查询和锁检查，可能影响性能
2. **内存管理**：类级别锁会占用内存，建议定期清理
3. **日志级别**：建议在生产环境中调整日志级别
4. **权限要求**：清理已过账账单需要相应权限
5. **数据一致性**：建议在维护窗口期间运行清理操作

## 监控建议

1. 定期运行测试脚本检查重复账单
2. 监控日志中的重复账单警告和锁状态
3. 定期清理账单更新锁，防止内存泄漏
4. 设置告警机制，当发现重复时及时通知
5. 监控锁的数量，如果过多可能表示存在问题
6. 定期审查账单创建逻辑的执行情况

## 故障排除

### 锁无法清除

如果发现锁无法正常清除：

```python
# 强制清理所有锁
env['account.move']._billing_update_locks.clear()

# 或者重启Odoo服务（会清除所有内存中的锁）
```

### 重复触发仍然存在

如果仍然存在重复触发：

1. 检查是否有其他模块也在调用账单更新方法
2. 查看日志中的锁状态信息
3. 确认锁的键值生成逻辑是否正确
4. 检查是否有异步任务在后台执行
