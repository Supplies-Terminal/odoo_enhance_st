import uuid
from odoo import api, models, fields

class StPurchasecard(models.Model):
    _name = "st.purchasecard"
    _description = "Purchase Card"

    website_id = fields.Many2one('website', ondelete='cascade', required=True)
    member_id = fields.Many2one('res.partner', string='Member', required=True)
    uuid = fields.Char(compute='_compute_uuid', store=True)
    data = fields.Text()

    def _compute_uuid(self):
        for record in self:
            if not record.uuid:
                record.uuid = str(uuid.uuid4())