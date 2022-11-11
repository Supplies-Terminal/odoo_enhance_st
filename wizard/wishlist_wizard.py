# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo.tools.translate import _
from odoo.tools import email_normalize
from odoo.exceptions import UserError

from odoo import api, fields, models, Command


_logger = logging.getLogger(__name__)


class WishlistWizard(models.TransientModel):
    _name = 'wishlist.wizard'
    _description = 'Init App Wishlist'

    def _default_partner_id(self):
        partner_id = self.env.context.get('active_id', 0)
        return partner_id

    partner_id = fields.Int(string='Partner', default=_default_partner_id)
    website_ids = fields.One2many('wishlist.wizard.user', 'wizard_id', string='Websites', compute='_compute_website_ids', store=True, readonly=False)

    @api.depends('partner_ids')
    def _compute_website_ids(self):
        for wishlist_wizard in self:
            partner = self.env['res.partner'].sudo().browse(wishlist_wizard.partner_id)

            if partner:
                wishlist_wizard.website_ids = [
                    Command.create({
                        'website_id': website.id,
                        'website_name': website.name,
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
            'name': _('Portal Access Management'),
            'type': 'ir.actions.act_window',
            'res_model': 'wishlist.wizard',
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }


class WishlistWizardUser(models.TransientModel):
    """
        A model to configure users in the wishlist wizard.
    """

    _name = 'wishlist.wizard.user'
    _description = 'Portal User Config'

    wizard_id = fields.Many2one('wishlist.wizard', string='Wizard', required=True, ondelete='cascade')
    partner_id = fields.Many2one('res.partner', string='Contact', required=True, readonly=True, ondelete='cascade')
    email = fields.Char('Email')

    user_id = fields.Many2one('res.users', string='User', compute='_compute_user_id', compute_sudo=True)
    login_date = fields.Datetime(related='user_id.login_date', string='Latest Authentication')
    is_wishlist = fields.Boolean('Is Portal', compute='_compute_group_details')
    is_internal = fields.Boolean('Is Internal', compute='_compute_group_details')

    @api.depends('partner_id')
    def _compute_user_id(self):
        for wishlist_wizard_user in self:
            user = wishlist_wizard_user.partner_id.with_context(active_test=False).user_ids
            wishlist_wizard_user.user_id = user[0] if user else False

    @api.depends('user_id', 'user_id.groups_id')
    def _compute_group_details(self):
        for wishlist_wizard_user in self:
            user = wishlist_wizard_user.user_id

            if user and user.has_group('base.group_user'):
                wishlist_wizard_user.is_internal = True
                wishlist_wizard_user.is_wishlist = False
            elif user and user.has_group('base.group_wishlist'):
                wishlist_wizard_user.is_internal = False
                wishlist_wizard_user.is_wishlist = True
            else:
                wishlist_wizard_user.is_internal = False
                wishlist_wizard_user.is_wishlist = False

    def action_init_wishlist(self):
        self.ensure_one()

        return self.wizard_id._action_open_modal()
