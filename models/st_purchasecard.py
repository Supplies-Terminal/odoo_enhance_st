import uuid
from odoo import api, models, fields

class StPurchasecard(models.Model):
    _name = "st.purchasecard"
    _description = "Purchase Card"
    _rec_name = 'name'

    def _generate_uuid(self):
        return str(uuid.uuid4())

    website_id = fields.Many2one('website', ondelete='cascade', required=True)
    member_id = fields.Many2one('res.partner', string='Member', required=True)
    uuid = fields.Char(default=_generate_uuid)
    data = fields.Text()
    name = fields.Char(compute='_compute_name', store=False)

    @api.depends('website_id', 'member_id')
    def _compute_name(self):
        for rec in self:
            if (rec.member_id.ref):
                rec.name = "%s - %s (%s)" % (rec.website_id.name, rec.member_id.name, rec.member_id.ref)
            else:
                rec.name = "%s - %s" % (rec.website_id.name, rec.member_id.name)
