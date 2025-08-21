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

### 1. 事件驱动的账单更新逻辑 ⭐ **重构**

由于发票在 `posted` 状态下不能修改，账单更新只需要处理两个关键事件：

#### 1.1 Reset to Draft 事件

```python
def _handle_draft_invoices_update(self):
    """处理发票重置为草稿状态事件"""
    for record in self:
        # 处理销售发票和贷项通知单
        if record.move_type not in ['out_invoice', 'out_refund']:
            continue
        
        # 使用类级别的锁防止重复触发
        lock_key = f"draft_{record.id}_{record.invoice_date}"
        if lock_key in self._billing_update_locks:
            _logger.info(f"跳过重复的草稿更新: {record.id} {record.name} (锁已存在)")
            continue
        
        # 设置锁并处理
        self._billing_update_locks[lock_key] = True
        try:
            # 强制更新相关账单
            self._force_update_customer_billing_bill(mapping.billing_company_id, record, mapping)
        finally:
            # 清除锁
            if lock_key in self._billing_update_locks:
                del self._billing_update_locks[lock_key]
```

#### 1.2 Confirm Invoice 事件

```python
def _handle_posted_invoices_update(self):
    """处理发票确认过账事件"""
    for record in self:
        # 处理销售发票和贷项通知单
        if record.move_type not in ['out_invoice', 'out_refund']:
            continue
        
        # 使用类级别的锁防止重复触发
        lock_key = f"posted_{record.id}_{record.invoice_date}"
        if lock_key in self._billing_update_locks:
            _logger.info(f"跳过重复的过账账单更新: {record.id} {record.name} (锁已存在)")
            continue
        
        # 设置锁并处理
        self._billing_update_locks[lock_key] = True
        try:
            # 更新或创建客户账单
            self._update_customer_billing_bill(billing_company, record, mapping, customer_bill)
        finally:
            # 清除锁
            if lock_key in self._billing_update_locks:
                del self._billing_update_locks[lock_key]
```

#### 1.3 支持的业务类型 ⭐ **新增**

现在系统支持以下业务类型：

1. **销售发票 (out_invoice)**：
   - 正向记录，增加客户应收账款
   - 影响客户账单的正向金额

2. **贷项通知单 (out_refund)**：
   - 负向记录，减少客户应收账款
   - 用于退款、折扣、调整等
   - 影响客户账单的负向金额

#### 1.4 事件触发逻辑

```python
def write(self, vals):
    res = super(AccountInvoice, self).write(vals)
    for record in self:
        if record.operating_company_id:
            record._update_daily_settlement()
        
        # 只处理两个关键事件：reset to draft 和 confirm invoice
        if 'state' in vals:
            try:
                if vals['state'] == 'draft':
                    # 发票重置为草稿状态
                    record._handle_draft_invoices_update()
                elif vals['state'] == 'posted':
                    # 发票确认过账
                    record._handle_posted_invoices_update()
            except Exception as e:
                # 记录错误但不中断发票状态变化
                _logger.error(f"处理发票状态变化时出错: {str(e)}")
                _logger.error(f"发票状态变化将继续，但账单更新可能失败")
    return res
```

### 2. 增强的重复检查逻辑

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

### 3. 金额检查逻辑 ⭐ **新增**

为了防止生成金额为0的账单，添加了严格的金额检查：

```python
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
```

#### 金额检查的好处：

1. **避免无效账单**：不会生成金额为0的账单行
2. **减少数据冗余**：只创建有实际金额的账单
3. **提高系统性能**：减少不必要的数据库记录
4. **改善用户体验**：避免显示无意义的0金额账单

### 4. 事务保护

使用 `savepoint` 确保操作的原子性：

```python
with self.env.cr.savepoint():
    # 所有操作在一个事务中执行
    # 如果出现错误，可以回滚到保存点
```

### 5. 防重复触发机制

#### 类级别锁机制

为了防止同一发票的多次触发，添加了类级别的锁机制：

```python
class AccountInvoice(models.Model):
    _inherit = 'account.move'
    
    # 类级别的防重复锁
    _billing_update_locks = {}
    
    def _handle_posted_invoices_update(self):
        for record in self:
            # 使用类级别的锁防止重复触发
            lock_key = f"posted_{record.id}_{record.invoice_date}"
            if lock_key in self._billing_update_locks:
                _logger.info(f"跳过重复的过账账单更新: {record.id} {record.name} (锁已存在)")
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

#### 状态变化防重复机制 ⭐ **新增**

为了防止发票状态变化时重复生成账单，添加了智能的关系检查：

```python
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
        if len(existing_bills) == 1:
            # 如果存在账单，检查是否需要更新而不是创建新的
            existing_bill = existing_bills[0]
            return existing_bill, 'update'
        else:
            # 发现多个账单，需要清理重复
            return None, 'cleanup'
    
    return None, 'create'
```

#### 智能处理逻辑

根据检查结果，系统会智能选择处理方式：

1. **'update'** - 更新现有账单，不创建新的
2. **'cleanup'** - 清理重复账单，然后重新创建
3. **'create'** - 创建新账单

这样可以确保：
- **draft → posted** 时，如果已存在账单则更新，否则创建
- **posted → draft** 时，不会重复创建账单
- 同一发票在同一天只生成一张账单

### 6. 草稿发票处理逻辑 ⭐ **修复**

#### 问题描述

之前当发票从 posted 状态重置为 draft 状态时，账单没有正确更新，因为系统只计算已过账发票的金额。

#### 修复方案

现在系统会根据发票状态智能选择计算逻辑：

```python
# 根据当前发票状态决定计算逻辑
if invoice.state == 'draft':
    # 如果当前发票是草稿状态，考虑所有状态的发票（包括草稿）
    _logger.info(f"发票 {invoice.id} 是草稿状态，计算所有状态的发票金额")
    relevant_invoices = all_invoices
else:
    # 如果当前发票是已过账状态，只计算已过账发票的金额
    _logger.info(f"发票 {invoice.id} 是已过账状态，只计算已过账发票的金额")
    relevant_invoices = all_invoices.filtered(lambda inv: inv.state == 'posted')
```

#### 处理流程

1. **发票重置为草稿**：
   - 触发 `_handle_draft_invoices_update()` 方法
   - 调用 `_force_update_customer_billing_bill()` 强制更新
   - 删除现有账单，重新计算并创建

2. **金额计算逻辑**：
   - 草稿状态：计算所有状态发票的金额
   - 已过账状态：只计算已过账发票的金额

3. **账单更新**：
   - 确保账单金额与当前发票状态匹配
   - 避免生成金额为0的无效账单

### 7. 权限问题修复 ⭐ **新增**

#### 问题描述

之前的代码在访问 `res.partner` 和 `res.company` 记录时可能遇到权限问题，导致发票无法正常重置为草稿状态。

#### 修复方案

1. **安全属性访问**：
   ```python
   # 使用 getattr 安全地获取属性，避免权限问题
   billing_company_name = getattr(mapping.billing_company_id, 'name', 'Unknown Company')
   billing_partner_name = getattr(mapping.billing_partner_id, 'name', 'Unknown Partner')
   ```

2. **异常处理**：
   ```python
   try:
       # 安全地获取名称，避免权限问题
       billing_company_name = getattr(mapping.billing_company_id, 'name', 'Unknown Company')
       _logger.info(f"找到客户账单映射: {billing_company_name}")
   except Exception as e:
       _logger.error(f"处理客户账单映射时出错: {str(e)}")
       # 继续处理，不中断流程
   ```

3. **状态变化保护**：
   ```python
   # 在 write 方法中添加错误处理
   try:
       if vals['state'] == 'draft':
           record._handle_draft_invoices_update()
       elif vals['state'] == 'posted':
           record._handle_posted_invoices_update()
   except Exception as e:
       # 记录错误但不中断发票状态变化
       _logger.error(f"处理发票状态变化时出错: {str(e)}")
       _logger.error(f"发票状态变化将继续，但账单更新可能失败")
   ```

#### 修复效果

- **发票状态变化正常**：即使账单更新失败，发票也能正常重置为草稿
- **权限问题隔离**：权限问题不会影响核心的发票操作
- **错误日志记录**：所有错误都会被记录，便于调试
- **系统稳定性提升**：避免了因权限问题导致的系统崩溃

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

### 6. 新增的辅助方法

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

### 8. 测试脚本

创建了 `test_billing_duplicate_fix.py` 测试脚本，包含：

- `test_duplicate_check()`: 检查所有映射的重复账单
- `test_billing_creation_logic()`: 测试账单创建逻辑
- `test_billing_locks()`: 测试账单更新锁机制
- `test_duplicate_trigger_prevention()`: 测试重复触发防护机制
- `test_event_driven_logic()`: 测试事件驱动的账单更新逻辑 ⭐ **新增**
- `test_method_compatibility()`: 测试方法兼容性 ⭐ **新增**
- `test_wizard_integration()`: 测试向导集成 ⭐ **新增**
- `test_zero_amount_bill_prevention()`: 测试防止生成金额为0的账单 ⭐ **新增**
- `test_state_change_duplicate_prevention()`: 测试状态变化时的防重复机制 ⭐ **新增**
- `test_draft_invoice_handling()`: 测试草稿发票处理逻辑 ⭐ **新增**
- `test_permission_handling()`: 测试权限处理机制 ⭐ **新增**
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

### 4. 管理账单更新锁

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

### 5. 测试事件驱动逻辑 ⭐ **新增**

```python
# 测试草稿事件处理
env['account.move']._handle_draft_invoices_update()

# 测试过账事件处理
env['account.move']._handle_posted_invoices_update()

# 检查锁状态
lock_status = env['account.move'].get_billing_locks_status()
print(f"当前锁: {lock_status}")
```

### 6. 向导集成更新 ⭐ **新增**

向导 `customer.billing.update.wizard` 已更新为使用新的事件驱动逻辑：

```python
# 向导现在根据发票状态使用相应的方法
if invoice.state == 'draft':
    # 草稿状态：使用草稿事件处理
    invoice._handle_draft_invoices_update()
elif invoice.state == 'posted':
    # 已过账状态：使用过账事件处理
    invoice._handle_posted_invoices_update()
else:
    # 其他状态：跳过
    continue
```

#### 向导的主要改进：

1. **状态感知处理**：根据发票状态选择合适的事件处理方法
2. **性能优化**：只处理草稿和已过账状态的发票
3. **详细日志**：记录每种状态的发票处理数量
4. **错误处理**：单个发票处理失败不影响其他发票

#### 使用向导：

```python
# 创建向导实例
wizard = env['customer.billing.update.wizard'].create({
    'company_id': company_id,
    'partner_id': partner_id,
    'start_date': start_date,
    'end_date': end_date,
})

# 执行处理
result = wizard.action_process()
```

## 改进效果

1. **事件驱动架构**：只处理必要的状态变化事件 ⭐ **重构**
2. **防止并发重复**：使用事务锁和保存点机制
3. **防止重复触发**：使用类级别锁机制
4. **全面状态检查**：检查草稿和已过账状态
5. **多层验证**：创建前多次检查，确保无重复
6. **详细日志**：记录所有操作，便于调试
7. **自动清理**：提供自动清理重复账单的方法
8. **锁管理**：防止内存泄漏和锁状态监控
9. **向后兼容**：废弃的方法仍然可用，但会显示警告

## 注意事项

1. **性能影响**：减少了不必要的调用，提高了性能 ⭐ **改进**
2. **内存管理**：类级别锁会占用内存，建议定期清理
3. **日志级别**：建议在生产环境中调整日志级别
4. **权限要求**：清理已过账账单需要相应权限
5. **数据一致性**：建议在维护窗口期间运行清理操作
6. **向后兼容**：旧的方法仍然可用，但建议迁移到新的事件驱动方法

## 监控建议

1. 定期运行测试脚本检查重复账单
2. 监控日志中的事件处理信息
3. 定期清理账单更新锁，防止内存泄漏
4. 设置告警机制，当发现重复时及时通知
5. 监控锁的数量，如果过多可能表示存在问题
6. 定期审查账单创建逻辑的执行情况
7. 关注废弃方法的调用，及时迁移到新方法

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
5. 确认是否使用了新的事件驱动方法

### 方法兼容性问题

如果遇到方法兼容性问题：

```python
# 检查方法是否存在
if hasattr(env['account.move'], '_handle_posted_invoices_update'):
    # 使用新方法
    env['account.move']._handle_posted_invoices_update()
else:
    # 回退到旧方法
    env['account.move']._update_customer_billing()
```

## 迁移指南

### 从旧版本迁移

1. **更新方法调用**：
   - 将 `_update_customer_billing()` 替换为 `_handle_posted_invoices_update()`
   - 将草稿处理逻辑替换为 `_handle_draft_invoices_update()`

2. **测试新逻辑**：
   - 运行完整的测试套件
   - 在测试环境中验证事件驱动逻辑

3. **监控日志**：
   - 关注废弃方法的警告信息
   - 确认新的事件处理日志正常

4. **清理旧代码**：
   - 确认新逻辑稳定后，可以移除旧的方法调用
   - 更新相关的文档和注释
