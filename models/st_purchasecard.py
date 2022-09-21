from odoo import api, models, fields

class StPurchasecard(models.Model):
    _name = "st.purchasecard"
    _description = "ST Purchase Card"

    supplier_id = fields.Many2one('res.partner', string='Supplier')
    member_id = fields.Many2one('res.partner', string='Member')
    uuid = fields.Char()
    data = fields.Text()
