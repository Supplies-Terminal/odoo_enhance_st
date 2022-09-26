from odoo import api, models, fields

class StPreference(models.Model):
    _name = "st.preference"
    _description = "ST Preferences"

    member_id = fields.Many2one('res.partner', string='Member')
    preferred_language = fields.Char()
    subscribe_order_notice = fields.Boolean()
    subscribe_other = fields.Boolean()
    subscribe_to = fields.Char()
