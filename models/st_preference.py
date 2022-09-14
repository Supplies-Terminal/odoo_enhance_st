from odoo import models, fields

class StPreference(models.Model):
    _name = "st.preference"
    _description = "ST Preferences"

    subscribe_order_notice = fields.Boolean()
    subscribe_other = fields.Boolean()
    subscribe_to = fields.Char()
