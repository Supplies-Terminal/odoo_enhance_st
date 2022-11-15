# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo.tools.translate import _
from odoo.tools import email_normalize
from odoo.exceptions import UserError

from odoo import api, fields, models, Command
from odoo.addons.website_sale_wishlist.controllers.main import WebsiteSaleWishlist


_logger = logging.getLogger(__name__)


class WishlistWizard(models.TransientModel):
    _name = 'wishlist.wizard'
    _description = 'Init App Wishlist'

    def _default_partner_id(self):
        partner_id = self.env.context.get('active_id', 0)
        return partner_id

    partner_id = fields.Integer(string='Partner', default=_default_partner_id)
    website_ids = fields.One2many('wishlist.wizard.website', 'wizard_id', string='Websites', compute='_compute_website_ids', store=True, readonly=False)

    @api.depends('partner_id')
    def _compute_website_ids(self):
        for wishlist_wizard in self:
            partner = self.env['res.partner'].sudo().browse(wishlist_wizard.partner_id)

            if partner:
                wishlist_wizard.website_ids = [
                    Command.create({
                        'partner_id': wishlist_wizard.partner_id,
                        'website_id': website.id,
                    })
                    for website in partner.website_ids
                ]
            else:
                wishlist_wizard.website_ids = []

    @api.model
    def action_open_wizard(self):
        """Create a "wishlist.wizard" and open the form view.

        We need a server action for that because the one2many "user_ids" records need to
        exist to be able to execute an a button action on it. If they have no ID, the
        buttons will be disabled and we won't be able to click on them.

        That's why we need a server action, to create the records and then open the form
        view on them.
        """
        wishlist_wizard = self.create({})
        return wishlist_wizard._action_open_modal()

    def _action_open_modal(self):
        """Allow to keep the wizard modal open after executing the action."""
        self.refresh()
        return {
            'name': _('Init wishlist in a website'),
            'type': 'ir.actions.act_window',
            'res_model': 'wishlist.wizard',
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }


class WishlistWizardWebsite(models.TransientModel):
    """
        A model to configure users in the wishlist wizard.
    """

    _name = 'wishlist.wizard.website'
    _description = 'Portal Website Config'

    wizard_id = fields.Many2one('wishlist.wizard', string='Wizard', required=True, ondelete='cascade')
    partner_id = fields.Many2one('res.partner', string='Contact', required=True, readonly=True, ondelete='cascade')
    website_id = fields.Many2one('website', string='Website', required=True, readonly=True, ondelete='cascade')
    total = fields.Integer(string="Items", compute="_compute_total")
    
    @api.depends("partner_id", "website_id")
    def _compute_total(self):
        for record in self:
            _logger.info("------------------------")
            _logger.info(record.partner_id.id)
            _logger.info(record.website_id.id)
            productsInWishlist = self.env['product.wishlist'].search([('website_id', '=', record.website_id.id), ('partner_id', '=', record.partner_id.id)])
            record.total = len(productsInWishlist)
    
    def _get_pricelist_context(self):
        _logger.info("------------6.1------------")
        pricelist_context = dict()
        pricelist = self.website_id.get_current_pricelist()
        pricelist_context['pricelist'] = pricelist.id
        _logger.info("------------6.2------------")
        return pricelist_context, pricelist 
               
    def action_init_wishlist(self):
        self.ensure_one()
        _logger.info("------------------------")
        _logger.info(self.partner_id)
        _logger.info(self.website_id)
        
        # get all products by website id
        products = self.env['product.product'].sudo().search([('website_id', '=', self.website_id.id)])
        Wishlist = self.env['product.wishlist']
        # get all products in wishlist by website id
        productsInWishlist = Wishlist.search([('website_id', '=', self.website_id.id), ('partner_id', '=', self.partner_id.id)])
        
        productIdsInWishlist = []
        for item in productsInWishlist:
            productIdsInWishlist.append(item.product_id.id)

        _logger.info(productIdsInWishlist)
            
        for product in products:
            product_id = product.id
            if product_id not in productIdsInWishlist:
                _logger.info(product_id)
                pricelist_context, pl = self._get_pricelist_context()
                p = self.env['product.product'].with_context(pricelist_context, display_default_code=False).browse(product_id)
                price = p._get_combination_info_variant()['price']
                _logger.info(price)

                wish_id = Wishlist._add_to_wishlist(
                    pl.id,
                    pl.currency_id.id,
                    self.website_id.id,
                    price,
                    product_id,
                    self.partner_id.id
                )
        
        return self.wizard_id._action_open_modal()
