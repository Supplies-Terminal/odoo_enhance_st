from odoo import models, fields

class StWishlist(models.Model):
    _name = "st.wishlist"
    _description = "ST Wishlist"

    member_id = fields.Many2one('res.partner', string='Member')
    product_id = fields.Many2one('product.product', string='Product', ondelete='cascade')
    is_system_set = fields.Boolean();

