# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'ST Enhanced Toolkit',
    'category': 'Website/Website',
    'sequence': 50,
    'summary': 'Enhanced user experiences based on the business operations.',
    'website': 'https://suppliesterminal.com',
    'version': '1.1.0',
    'description': "",
    'depends': [
        'base,
        'contacts',
        'website',
        ],
    'data': [
        'security/ir.model.access.csv',
        'views/res_partner_views.xml',
        'views/st_menu.xml',
        'views/st_purchasecard_views.xml',
        'views/templates.xml',
    ],
    'demo': [
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
