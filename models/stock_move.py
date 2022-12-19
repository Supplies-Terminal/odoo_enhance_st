# -*- coding: UTF-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api
import logging
_logger = logging.getLogger(__name__)

class StockMove(models.Model):
    _inherit = "stock.move"

    secondary_uom_enabled = fields.Boolean("Counting Unit Active")
    secondary_qty = fields.Float("Counts")
    secondary_uom_id = fields.Many2one("uom.uom", 'Counting Unit')
    secondary_uom_name = fields.Char("Counting Unit")
    secondary_uom_rate = fields.Float("Counting Unit Rate")
    secondary_done_qty = fields.Float("Counts Done")

    @api.model
    def create(self, vals):
        _logger.info('********stock.move.create*********')
        
        res = super(StockMove, self).create(vals)
        _logger.info(res.sale_line_id.secondary_uom_enabled)
        # 直接从sale order中复制过来
        if res.sale_line_id and res.sale_line_id.secondary_uom_enabled and res.sale_line_id.secondary_uom_id:
            _logger.info(res.sale_line_id.secondary_uom_enabled)
            _logger.info(res.sale_line_id.secondary_uom_id)
            _logger.info('-------------------------------')
            res.update({
                'secondary_uom_enabled': res.sale_line_id.secondary_uom_enabled,
                'secondary_uom_id': res.sale_line_id.secondary_uom_id.id,
                'secondary_uom_name': res.sale_line_id.secondary_uom_name.id,
                'secondary_uom_rate': res.sale_line_id.secondary_uom_rate.id,
                'secondary_qty': res.sale_line_id.secondary_qty
            })
        # elif res.purchase_line_id and res.purchase_line_id.secondary_uom_enabled and res.purchase_line_id.secondary_uom_id:
        #     res.update({
        #         'secondary_uom_id': res.purchase_line_id.secondary_uom_id.id,
        #         'secondary_qty': res.purchase_line_id.secondary_qty
        #     })
        return res


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    secondary_uom_enabled = fields.Boolean("Counting Unit Active")
    secondary_qty = fields.Float("Counts")
    secondary_uom_id = fields.Many2one("uom.uom", 'Counting Unit')
    secondary_uom_name = fields.Char("Counting Unit")
    secondary_uom_rate = fields.Float("Counting Unit Rate")
    secondary_done_qty = fields.Float("Counts Done")

    def _get_aggregated_product_quantities(self, **kwargs):
        _logger.info('********stock.move.line _get_aggregated_product_quantities *********')
        """ Returns a dictionary of products (key = id+name+description+uom) and corresponding values of interest.

        Allows aggregation of data across separate move lines for the same product. This is expected to be useful
        in things such as delivery reports. Dict key is made as a combination of values we expect to want to group
        the products by (i.e. so data is not lost). This function purposely ignores lots/SNs because these are
        expected to already be properly grouped by line.

        returns: dictionary {product_id+name+description+uom: {product, name, description, qty_done, product_uom}, ...}
        """
        super(StockMoveLine, self)._get_aggregated_product_quantities(**kwargs)
        aggregated_move_lines = {}
        for move_line in self:
            name = move_line.product_id.display_name
            description = move_line.move_id.description_picking
            if description == name or description == move_line.product_id.name:
                description = False
            uom = move_line.product_uom_id
            line_key = str(move_line.product_id.id) + "_" + name + (description or "") + "uom " + str(uom.id)

            if line_key not in aggregated_move_lines:
                aggregated_move_lines[line_key] = {'name': name,
                                                   'description': description,
                                                   'qty_done': move_line.qty_done,
                                                   'product_uom': uom.name,
                                                   'product': move_line.product_id,
                                                   'secondary_uom_enabled':move_line.product_id.secondary_uom_enabled,
                                                   'secondary_qty':move_line.secondary_qty,
                                                   'secondary_uom_id':move_line.product_id.secondary_uom_id.id,
                                                   'secondary_uom_name':move_line.product_id.secondary_uom_id.name,
                                                   }
            else:
                aggregated_move_lines[line_key]['qty_done'] += move_line.qty_done
        return aggregated_move_lines


# class StockImmediateTransfer(models.TransientModel):
#     _inherit = 'stock.immediate.transfer'

#     def process(self):
#         res = super(StockImmediateTransfer, self).process()
#         for picking_ids in self.pick_ids:
#             for moves in picking_ids.move_ids_without_package:
#                 if moves.secondary_uom_id:
#                     moves.secondary_done_qty = moves.product_uom._compute_quantity(
#                         moves.product_uom_qty,
#                         moves.secondary_uom_id
#                     )
#                 for move_lines in moves.move_line_ids:
#                     if move_lines.secondary_uom_id:
#                         move_lines.secondary_qty = move_lines.product_uom_id._compute_quantity(
#                             move_lines.qty_done,
#                             moves.secondary_uom_id
#                         )
#         return res
