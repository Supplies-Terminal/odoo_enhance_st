# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo.tools.translate import _
from odoo.tools import email_normalize
from odoo.exceptions import UserError

from odoo import api, fields, models, Command
from odoo.addons.website_sale_wishlist.controllers.main import WebsiteSaleWishlist


_logger = logging.getLogger(__name__)


class WishlistWizardProduct(models.TransientModel):
    _name = 'wishlist.wizard.product'
    _description = 'Add to all wishlist'

    def _default_product_id(self):
        product_id = self.env.context.get('active_id', 0)
        return product_id

    product_id = fields.Integer(string='Product', default=_default_product_id)


    @api.model
    def action_open_wizard(self):
        """Create a "wishlist.wizard.product" and open the form view.

        We need a server action for that because the one2many "user_ids" records need to
        exist to be able to execute an a button action on it. If they have no ID, the
        buttons will be disabled and we won't be able to click on them.

        That's why we need a server action, to create the records and then open the form
        view on them.
        """
        wishlist_wizard_product = self.create({})
        return wishlist_wizard_product._action_open_modal()

    def _action_open_modal(self):
        """Allow to keep the wizard modal open after executing the action."""
        self.refresh()
        return {
            'name': _('Add the product to relavant website\'s clients'),
            'type': 'ir.actions.act_window',
            'res_model': 'wishlist.wizard.product.website',
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }


class WishlistWizardProductWebsite(models.TransientModel):
    """
        A model to configure users in the wishlist wizard.
    """

    _name = 'wishlist.wizard.product.website'
    _description = 'Add product to all clients of the website'

    wizard_id = fields.Many2one('wishlist.wizard.product', string='Wizard', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.template', string='Product', required=True, readonly=True, ondelete='cascade')
    total = fields.Integer(string="Clients", compute="_compute_total")
    
    @api.depends("product_id")
    def _compute_total(self):
        for record in self:
            _logger.info("------------------------")
            _logger.info(record.product_id)
            recordsInWishlist = self.env['product.wishlist'].search([('website_id', '=', record.product_id.website.id), ('product_id', '=', record.product_id.id)])
            record.total = len(recordsInWishlist)

    def _get_pricelist_context(self):
        _logger.info("------------6.1------------")
        pricelist_context = dict()
        pricelist = self.product_id.website_id.get_current_pricelist()
        pricelist_context['pricelist'] = pricelist.id
        _logger.info("------------6.2------------")
        return pricelist_context, pricelist 

    def action_add_to_wishlist(self):
        self.ensure_one()
        _logger.info("------------------------")
        _logger.info(self.product_id)
        
        # get all products by website id
        partners = self.env['res.partner'].sudo().search([('website_id', '=', self.website_id.id)])
        Wishlist = self.env['product.wishlist']
        # get all products in wishlist by website id
        recordsInWishlist = Wishlist.search([('website_id', '=', self.product_id.website_id.id), ('product_id', '=', self.product_id.id)])
        
        partnersInWishlist = []
        for item in recordsInWishlist:
            partnersInWishlist.append(item.partner_id.id)

        _logger.info(partnersInWishlist)
            
        for partner in partners:
            partner_id = partner.id
            if partner_id not in partnersInWishlist:
                _logger.info(partner_id)
                pricelist_context, pl = self._get_pricelist_context()
                price = self.product_id._get_combination_info_variant()['price']
                _logger.info(price)

                wish_id = Wishlist._add_to_wishlist(
                    pl.id,
                    pl.currency_id.id,
                    self.product_id.website_id.id,
                    price,
                    self.product_id.id,
                    partner_id.id
                )
        
        return self.wizard_id._action_open_modal()
