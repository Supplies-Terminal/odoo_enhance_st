# Summary

This module is for enhancing the user experiences based on the business operations.

# Features

## Sub-Features

- List supplier/customer with "name (referrence)" on creating PO/SO form.
- Search product in multi-language names

## 配置

在odoo studio中，对应的界面（例如sale order界面）
需要在product的字段进行context设置

``` JSON
{   "with_quantity": True, "display_default_code": True }
```

## 常用脚本

### last vendor

```
# 在 Odoo shell 中执行以下代码
env = self.env

# 指定公司ID
company_id = 1
company = env['res.company'].browse(company_id)
print(f"{company.name}")

# 根据private_product_only属性决定查询条件
if company.private_product_only:
    # 如果只查询私有产品，则查询该公司的产品
    domain = [('company_id', '=', company_id)]
else:
    # 如果查询公共产品，则查询没有指定公司的产品
    domain = [('company_id', '=', False)]

# 获取产品模板
product_templates = env['product.template'].search(domain)

# 设置当前公司
env.company = company

# 循环处理每个产品模板
total = len(product_templates)
for i, template in enumerate(product_templates, 1):
    template._compute_last_vendor_id()
    env.cr.commit()  # 每处理一个就提交一次
    if i % 10 == 0:  # 每处理10个打印一次进度
        print(f"已处理 {i}/{total} 个产品")
```
