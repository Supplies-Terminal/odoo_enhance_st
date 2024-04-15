# -*- coding: utf-8 -*-
import json
import logging
from odoo import fields, http, tools, _
from odoo.addons.website.controllers.main import Website
from odoo.addons.auth_signup.controllers.main import AuthSignupHome

_logger = logging.getLogger(__name__)

# class WebsiteApproval(Website):

#     # Error Message
#     @http.route(website=True, auth="public", sitemap=False)
#     def web_login(self, *args, **kw):
#         res = super().web_login(*args, **kw)
#         if res.is_qweb and res.qcontext.get('error') == 'Not Approved User':
#             res.qcontext['error'] = (_("You are already registered! Please wait for approval."))
#         return res


# class AuthSignupApproval(AuthSignupHome):

#     # Error Message
#     @http.route('/web/signup', type='http', auth='public', website=True, sitemap=False)
#     def web_auth_signup(self, *args, **kw):
#         res = super().web_auth_signup(*args, **kw)
#         if res.is_qweb and res.qcontext.get('error') == 'Not Approved User':
#             res.qcontext['approval_msg'] = (_("You registered successfully! Wait for account approval."))
#             res.qcontext['error'] = False
#         return res
    
class Purchasecard(http.Controller):
    @http.route('/purchasecard/purchasecard/print/<uuid>/<locale>', auth='public')
    def list(self, uuid, locale, **kw):
        purchasecard = http.request.env['st.purchasecard'].search([('uuid', '=', uuid)], limit=1)
        if not purchasecard:
            return http.request.render('odoo_enhance_st.print-error', {
                'message': 'Data not found',
            })

        _logger.info(purchasecard.id)
        _logger.info('********purchasecard*********')
        _logger.info(purchasecard)
        _logger.info(purchasecard.uuid)
        _logger.info(purchasecard.website_id)
        website = purchasecard.website_id
        
        if not website:
            return http.request.render('odoo_enhance_st.print-error', {
                'message': 'Data error: website not exists',
            })
            
        _logger.info('********purchasecard 2*********')
        _logger.info(website.id)
        _logger.info(website.name)
        _logger.info('********purchasecard 2*********')
        
        def get_frontend_langs():
            return [code for code, _ in http.request.env['res.lang'].get_installed()]

        def get_nearest_lang(lang_code):
            """ Try to find a similar lang. Eg: fr_BE and fr_FR
                :param lang_code: the lang `code` (en_US)
            """
            if not lang_code:
                return False
            short_match = False
            short = lang_code.partition('_')[0]
            for code in get_frontend_langs():
                if code == lang_code:
                    return code
                if not short_match and code.startswith(short):
                    short_match = code
            return short_match

        locale = get_nearest_lang(locale)
        if not locale:
            locale = 'en_US'
            
        lines = 20
        # 获取指定语言的商品名称
        purchaseCardGrid = json.loads(purchasecard['data'])
        pages = {}
        
        for tableIndex in range(0, len(purchaseCardGrid)):
            pageIndex = tableIndex // 4
            if pageIndex not in pages:
                pages[pageIndex] = []
            
            total = len(purchaseCardGrid[tableIndex]['items'])
            for itemIndex in range(0, total-1):
                if purchaseCardGrid[tableIndex]['items'][itemIndex]['product_id']:
                    productInfo = http.request.env['product.product'].with_context(lange=locale).browse(int(purchaseCardGrid[tableIndex]['items'][itemIndex]['product_id']))
                    if productInfo:
                        purchaseCardGrid[tableIndex]['items'][itemIndex]['name'] = productInfo['name']
                        purchaseCardGrid[tableIndex]['items'][itemIndex]['unit'] = productInfo['uom_name']
            # 补全空行
            if total < lines:
                for other in range(total, lines):
                    purchaseCardGrid[tableIndex]['items'].append({
                        'product_id': 0,
                        'name': '',
                        'unit': ''
                    })
            pages[pageIndex].append(purchaseCardGrid[tableIndex])

        _logger.info(json.dumps(pages))
               
        return http.request.render('odoo_enhance_st.print', {
            'uuid': uuid,
            'locale': locale,
            'website': website.name,
            'data': pages
        })
        
class InvoiceReportController(http.Controller):
    @http.route('/reports/customer_statement', type='json', auth='user')
    def customer_statement(self, invoice_ids):
        Invoice = request.env['account.move']
        invoices = Invoice.browse(invoice_ids)

        # Group invoices by customer
        customers = {}
        for inv in invoices:
            customer = inv.partner_id
            if customer.id not in customers:
                customers[customer.id] = {
                    'name': customer.name,
                    'invoices': [],
                }
            customers[customer.id]['invoices'].append(inv)

        # Render the report
        data = {'docs': list(customers.values())}
        pdf_content = request.env.ref('odoo_enhance_st.report_customer_statement').sudo()._render_qweb_pdf(data=data)[0]

        headers = [
            ('Content-Type', 'application/pdf'),
            ('Content-Length', len(pdf_content))
        ]

        return request.make_response(pdf_content, headers=headers)