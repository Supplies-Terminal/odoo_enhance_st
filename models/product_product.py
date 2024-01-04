# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import re

from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression

from odoo.tools import float_compare, float_round

_logger = logging.getLogger(__name__)

class ProductProduct(models.Model):
    _inherit = "product.product"

    stock_quantities = fields.Char(compute='_compute_stock_quantities', store=False)

    def _compute_stock_quantities(self):
        _logger.info('------_compute_stock_quantities-------')
        for product in self:
            quantities = []
            for company in self.env['res.company'].search([]):
                if company.warehouse_id.lot_stock_id:
                    qty = self.env['stock.quant'].sudo()._get_available_quantity(product, company.warehouse_id.lot_stock_id)
                    if qty:
                        quantities.append(f"{company.name.split()[0]}: {round(qty)}")
            product.stock_quantities = ', '.join(quantities)

    @api.model
    def name_get(self):
        # TDE: this could be cleaned a bit I think

        def _name_get(d):
            code = self._context.get('display_default_code', True) and d.get('default_code', False) or False

            # 获取多种语言的名称
            prod = self.browse(d['id'])
            name = prod['combined_name']

            # 附加商品编号  
            if code:
                name = '[%s] %s' % (code, name)

            # 这里增加界面选择区别（来自界面搜索的，增加附带库存信息）
            qtys = prod.stock_quantities
            
            return (d['id'], name)

        partner_id = self._context.get('partner_id')
        if partner_id:
            partner_ids = [partner_id, self.env['res.partner'].browse(partner_id).commercial_partner_id.id]
        else:
            partner_ids = []
        company_id = self.env.context.get('company_id')

        # all user don't have access to seller and partner
        # check access and use superuser
        self.check_access_rights("read")
        self.check_access_rule("read")

        result = []

        # Prefetch the fields used by the `name_get`, so `browse` doesn't fetch other fields
        # Use `load=False` to not call `name_get` for the `product_tmpl_id`
        self.sudo().read(['name', 'default_code', 'product_tmpl_id'], load=False)

        product_template_ids = self.sudo().mapped('product_tmpl_id').ids

        if partner_ids:
            supplier_info = self.env['product.supplierinfo'].sudo().search([
                ('product_tmpl_id', 'in', product_template_ids),
                ('name', 'in', partner_ids),
            ])
            # Prefetch the fields used by the `name_get`, so `browse` doesn't fetch other fields
            # Use `load=False` to not call `name_get` for the `product_tmpl_id` and `product_id`
            supplier_info.sudo().read(['product_tmpl_id', 'product_id', 'product_name', 'product_code'], load=False)
            supplier_info_by_template = {}
            for r in supplier_info:
                supplier_info_by_template.setdefault(r.product_tmpl_id, []).append(r)
        for product in self.sudo():
            variant = product.product_template_attribute_value_ids._get_combination_name()

            name = variant and "%s (%s)" % (product.name, variant) or product.name
            sellers = self.env['product.supplierinfo'].sudo().browse(self.env.context.get('seller_id')) or []
            if not sellers and partner_ids:
                product_supplier_info = supplier_info_by_template.get(product.product_tmpl_id, [])
                sellers = [x for x in product_supplier_info if x.product_id and x.product_id == product]
                if not sellers:
                    sellers = [x for x in product_supplier_info if not x.product_id]
                # Filter out sellers based on the company. This is done afterwards for a better
                # code readability. At this point, only a few sellers should remain, so it should
                # not be a performance issue.
                if company_id:
                    sellers = [x for x in sellers if x.company_id.id in [company_id, False]]
            if sellers:
                for s in sellers:
                    seller_variant = s.product_name and (
                        variant and "%s (%s)" % (s.product_name, variant) or s.product_name
                        ) or False
                    mydict = {
                              'id': product.id,
                              'name': seller_variant or name,
                              'default_code': s.product_code or product.default_code,
                              }
                    temp = _name_get(mydict)
                    if temp not in result:
                        result.append(temp)
            else:
                mydict = {
                          'id': product.id,
                          'name': name,
                          'default_code': product.default_code,
                          }
                result.append(_name_get(mydict))
        return result

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        if not args:
            args = []
        if name:
            _logger.info('******** product _name_search *********')
            context_lang = self._context.get("lang")
            installed_langs = self.env["res.lang"].get_installed()
            langs = [x[0] for x in installed_langs if x[0] != context_lang]
            _logger.info(langs)
        
            positive_operators = ['=', 'ilike', '=ilike', 'like', '=like']
            product_ids = []
            if operator in positive_operators:
                _logger.info(" * ")
                product_ids = list(self._search([('default_code', '=', name)] + args, limit=limit, access_rights_uid=name_get_uid))
                if not product_ids:
                    product_ids = list(self._search([('barcode', '=', name)] + args, limit=limit, access_rights_uid=name_get_uid))
            if not product_ids and operator not in expression.NEGATIVE_TERM_OPERATORS:
                _logger.info(" ** ")
                # Do not merge the 2 next lines into one single search, SQL search performance would be abysmal
                # on a database with thousands of matching products, due to the huge merge+unique needed for the
                # OR operator (and given the fact that the 'name' lookup results come from the ir.translation table
                # Performing a quick memory merge of ids in Python will give much better performance
                product_ids = list(self._search(args + [('default_code', operator, name)], limit=limit))
                if not limit or len(product_ids) < limit:
                    # we may underrun the limit because of dupes in the results, that's fine
                    limit2 = (limit - len(product_ids)) if limit else False
                    product2_ids = self._search(args + [('name', operator, name), ('id', 'not in', product_ids)], limit=limit2, access_rights_uid=name_get_uid)
                    product_ids.extend(product2_ids)

                    # 扩展其它语言的内容，扩充到结果中
                    _logger.info("扩展其它语言的内容，扩充到结果中")
                    for lang in langs:
                        res_lang = list(self.with_context(lang=lang)._search(args + [('name', operator, name), ('id', 'not in', product_ids)], limit=limit2, access_rights_uid=name_get_uid))
                        new_res = list(filter(lambda x: x not in product_ids, res_lang))
                        _logger.info(new_res)
                        product_ids.extend(new_res)
            elif not product_ids and operator in expression.NEGATIVE_TERM_OPERATORS:
                _logger.info(" *** ")
                domain = expression.OR([
                    ['&', ('default_code', operator, name), ('name', operator, name)],
                    ['&', ('default_code', '=', False), ('name', operator, name)],
                ])
                domain = expression.AND([args, domain])
                product_ids = list(self._search(domain, limit=limit, access_rights_uid=name_get_uid))

                # 扩展其它语言的内容，扩充到结果中
                _logger.info("扩展其它语言的内容，扩充到结果中")
                for lang in langs:
                    res_lang = list(self.with_context(lang=lang)._search(domain, limit=limit, access_rights_uid=name_get_uid))
                    new_res = list(filter(lambda x: x not in product_ids, res_lang))
                    _logger.info(new_res)
                    product_ids.extend(new_res)
            if not product_ids and operator in positive_operators:
                _logger.info(" **** ")
                ptrn = re.compile('(\[(.*?)\])')
                res = ptrn.search(name)
                if res:
                    product_ids = list(self._search([('default_code', '=', res.group(2))] + args, limit=limit, access_rights_uid=name_get_uid))

                    # 扩展其它语言的内容，扩充到结果中
                    _logger.info("扩展其它语言的内容，扩充到结果中")
                    for lang in langs:
                        res_lang = list(self.with_context(lang=lang)._search([('default_code', '=', res.group(2))] + args, limit=limit, access_rights_uid=name_get_uid))
                        new_res = list(filter(lambda x: x not in product_ids, res_lang))
                        _logger.info(new_res)
                        product_ids.extend(new_res)
            # still no results, partner in context: search on supplier info as last hope to find something
            if not product_ids and self._context.get('partner_id'):
                _logger.info(" ***** ")
                suppliers_ids = self.env['product.supplierinfo']._search([
                    ('name', '=', self._context.get('partner_id')),
                    '|',
                    ('product_code', operator, name),
                    ('product_name', operator, name)], access_rights_uid=name_get_uid)
                if suppliers_ids:
                    product_ids = self._search([('product_tmpl_id.seller_ids', 'in', suppliers_ids)], limit=limit, access_rights_uid=name_get_uid)
        else:
            product_ids = self._search(args, limit=limit, access_rights_uid=name_get_uid)
        return product_ids
