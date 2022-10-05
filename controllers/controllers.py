# -*- coding: utf-8 -*-
from odoo import http
import json
import logging

_logger = logging.getLogger(__name__)

class Purchasecard(http.Controller):
    @http.route('/purchasecard/purchasecard/print/<uuid>/<locale>', auth='public')
    def list(self, uuid, locale, **kw):
        purchasecard = http.request.env['st.purchasecard'].search([('uuid', '=', uuid)], limit=1)
        if not purchasecard:
            return http.request.render('purchasecard.print-error', {
                'message': 'Data not found',
            })

        _logger.info(purchasecard.id)
        _logger.info('********purchasecard*********')
        _logger.info(purchasecard)
        _logger.info(purchasecard.uuid)
        _logger.info(purchasecard.website_id)
        website = purchasecard.website_id
        
        if not website:
            return http.request.render('purchasecard.print-error', {
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
        
        for tableIndex in range(0, len(purchaseCardGrid)-1):
            pageIndex = tableIndex % 4
            if pageIndex not in pages:
                pages[pageIndex] = []
            
            total = len(purchaseCardGrid[tableIndex]['items'])
            for itemIndex in range(0, total-1):
                productInfo = http.request.env['product.product'].with_context(lange=locale).browse(purchaseCardGrid[tableIndex]['items'][itemIndex]['product_id'])
                if productInfo:
                    purchaseCardGrid[tableIndex]['items'][itemIndex]['name'] = productInfo['name']
            # 补全空行
            if total < lines:
                for other in range(total, lines):
                    purchaseCardGrid[tableIndex]['items'].append({
                        'product_id': 0,
                        'name': '&nbsp;',
                        'unit': '&nbsp;'
                    })
            pages[pageIndex].append(purchaseCardGrid[tableIndex])

        _logger.info(json.dumps(pages))
               
        return http.request.render('purchasecard.print', {
            'uuid': uuid,
            'locale': locale,
            'website': website.name,
            'data': purchaseCardGrid
        })
        
