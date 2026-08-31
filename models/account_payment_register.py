# -*- coding: utf-8 -*-

from odoo import _, models
from odoo.exceptions import AccessError


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    def _check_invoice_no_payment_group(self):
        if not self.env.su and self.env.user.has_group("odoo_enhance_st.group_invoice_no_payment"):
            raise AccessError(_("You are not allowed to register payments."))

    def default_get(self, fields_list):
        self._check_invoice_no_payment_group()
        return super().default_get(fields_list)

    def action_create_payments(self):
        self._check_invoice_no_payment_group()
        return super().action_create_payments()

    def _create_payments(self):
        self._check_invoice_no_payment_group()
        return super()._create_payments()
