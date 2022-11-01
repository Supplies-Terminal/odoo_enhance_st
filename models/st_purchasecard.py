import uuid
from odoo import api, models, fields

class StPurchasecard(models.Model):
    _name = "st.purchasecard"
    _description = "Purchase Card"

    def _generate_uuid(self):
        return str(uuid.uuid4())

    website_id = fields.Many2one('website', ondelete='cascade', required=True)
    member_id = fields.Many2one('res.partner', string='Member', required=True)
    uuid = fields.Char(default=_generate_uuid)
    data = fields.Text()