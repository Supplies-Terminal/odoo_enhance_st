# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class IrTranslation(models.Model):
    _inherit = 'ir.translation'

    PRODUCT_NAME_KEYS = (
        'product.template,name',
        'product.product,name',
    )

    def _get_product_template_ids(self):
        """Collect product.template ids whose name translation changed."""
        template_ids = set()
        ProductProduct = self.env['product.product'].sudo()
        for rec in self:
            if rec.name not in self.PRODUCT_NAME_KEYS or not rec.res_id:
                continue
            if rec.type and rec.type not in ('model', 'model_terms'):
                continue
            if rec.name == 'product.template,name':
                template_ids.add(rec.res_id)
            else:
                product = ProductProduct.browse(rec.res_id)
                if product.exists() and product.product_tmpl_id:
                    template_ids.add(product.product_tmpl_id.id)
        return list(template_ids)

    def _recompute_product_combined_name(self):
        template_ids = self._get_product_template_ids()
        if not template_ids:
            return
        templates = self.env['product.template'].sudo().browse(template_ids).exists()
        if templates:
            templates._compute_combined_name()

    @api.model_create_multi
    def create(self, vals_list):
        records = super(IrTranslation, self).create(vals_list)
        records._recompute_product_combined_name()
        return records

    def write(self, vals):
        old_templates = self.env['product.template']
        if any(key in vals for key in ('res_id', 'name')):
            old_templates = self.env['product.template'].sudo().browse(
                self._get_product_template_ids()
            )
        res = super(IrTranslation, self).write(vals)
        if any(key in vals for key in ('value', 'src', 'res_id', 'name', 'lang')):
            new_ids = self._get_product_template_ids()
            templates = (old_templates | self.env['product.template'].sudo().browse(new_ids)).exists()
            if templates:
                templates._compute_combined_name()
        return res

    def unlink(self):
        template_ids = self._get_product_template_ids()
        res = super(IrTranslation, self).unlink()
        templates = self.env['product.template'].sudo().browse(template_ids).exists()
        if templates:
            templates._compute_combined_name()
        return res
