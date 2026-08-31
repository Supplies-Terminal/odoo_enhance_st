# -*- coding: utf-8 -*-

from odoo import _, api, models
from odoo.exceptions import AccessError


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def _check_invoice_no_payment_group(self):
        if not self.env.su and self.env.user.has_group("odoo_enhance_st.group_invoice_no_payment"):
            raise AccessError(_("You are not allowed to operate payments."))

    @api.model_create_multi
    def create(self, vals_list):
        self._check_invoice_no_payment_group()
        return super().create(vals_list)

    def write(self, vals):
        self._check_invoice_no_payment_group()
        return super().write(vals)

    def unlink(self):
        self._check_invoice_no_payment_group()
        return super().unlink()

    def action_post(self):
        self._check_invoice_no_payment_group()
        return super().action_post()

    def action_cancel(self):
        self._check_invoice_no_payment_group()
        return super().action_cancel()

    def action_draft(self):
        self._check_invoice_no_payment_group()
        return super().action_draft()
