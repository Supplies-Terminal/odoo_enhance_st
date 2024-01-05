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
