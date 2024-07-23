# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'ST Enhanced Toolkit',
    'category': 'Website/Website',
    'sequence': 50,
    'summary': 'Enhanced user experiences based on the business operations.',
    'website': 'https://suppliesterminal.com',
    'version': '1.2.0',
    'description': """
        包含下面的功能：
        - 产品多语言名字整合，能多语言搜索，多处使用，多行显示
        - 产品计量单位支持
        - App用户采购卡
        - App用户申请审批
        - 内部跨公司采购
        - 跨公司调度
        - 客户statement
        - 多公司对公共商品的访问控制
        - virtual company模式支持：
            - 替销售公司下单
            - 替销售公司打印订单
    """,
    'depends': [
        'contacts',
        'website',
        'sale',
        'web',
        'rma'
    ],
    'data': [
        'security/ir.model.access.csv',
        'reports/report_customer_statement.xml',
        'reports/report_purchase_order_allocation.xml',
        'views/res_partner_views.xml',
        'views/st_menu.xml',
        'views/st_purchasecard_views.xml',
        'views/templates.xml',
        'data/mail_template.xml',
        'views/res_user_approval.xml',
        'views/template.xml',
        'views/product_template_views.xml',
        'views/purchase_order_views.xml',
        'views/sale_order_views.xml',
        'views/product_template_views.xml',
        'views/stock_orderpoint_views.xml',
        'wizard/stock_orderpoint_replace_views.xml',
        'views/mrp_bom_views.xml',
        'wizard/wishlist_wizard_views.xml',
        'wizard/wishlist_wizard_product_views.xml',
        'wizard/stock_daily_report_wizard.xml',
        'views/daily_stock_report_views.xml',
        'views/res_company_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'odoo_enhance_st/static/src/js/product_configurator_widget.js',
        ],
    },
    'demo': [
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
