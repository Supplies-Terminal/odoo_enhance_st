# -*- coding: UTF-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, models, fields, api
from odoo.exceptions import UserError, ValidationError
import logging
_logger = logging.getLogger(__name__)

class StockMove(models.Model):
    _inherit = "stock.move" 

    secondary_uom_enabled = fields.Boolean("Enable Counting Unit")
    secondary_qty = fields.Float("Secondary QTY")
    secondary_uom_id = fields.Many2one("uom.uom", 'Secondary UoM')
    secondary_uom_name = fields.Char("Secondary Unit")
    secondary_uom_rate = fields.Float("Secondary UoM Rate")
    secondary_done_qty = fields.Float("Secondary QTY Done")

    @api.model
    def create(self, vals):
        _logger.info('********stock.move.create*********')
        
        res = super(StockMove, self).create(vals)
        # _logger.info(res)
        # _logger.info(res.sale_line_id)
        # _logger.info(vals)
        # _logger.info(res.move_dest_ids)
        # 直接从sale order中复制过来
        if res.sale_line_id and res.sale_line_id.secondary_uom_enabled and res.sale_line_id.secondary_uom_id:
            # _logger.info('--------------sale_line_id-----------------')
            # _logger.info(res.sale_line_id.secondary_uom_enabled)
            # _logger.info(res.sale_line_id.secondary_uom_id)
            # _logger.info(res.sale_line_id.secondary_uom_name)
            # _logger.info(res.sale_line_id.secondary_uom_rate)
            # _logger.info(res.sale_line_id.secondary_qty)
            res.write({
                'secondary_uom_enabled': res.sale_line_id.secondary_uom_enabled,
                'secondary_uom_id': res.sale_line_id.secondary_uom_id.id,
                'secondary_uom_name': res.sale_line_id.secondary_uom_name,
                'secondary_uom_rate': res.sale_line_id.secondary_uom_rate,
                'secondary_qty': res.sale_line_id.secondary_qty
            })
        elif res.move_dest_ids:
            for move_dest in res.move_dest_ids:
                if move_dest.secondary_uom_enabled and move_dest.secondary_uom_id:
                    # _logger.info(('--------------move_dest-----------------'))
                    # _logger.info(move_dest.secondary_uom_enabled)
                    # _logger.info(move_dest.secondary_uom_id)
                    # _logger.info(move_dest.secondary_uom_name)
                    # _logger.info(move_dest.secondary_uom_rate)
                    # _logger.info(move_dest.secondary_qty)
                    res.write({
                        'secondary_uom_enabled': move_dest.secondary_uom_enabled,
                        'secondary_uom_id': move_dest.secondary_uom_id.id,
                        'secondary_uom_name': move_dest.secondary_uom_name,
                        'secondary_uom_rate': move_dest.secondary_uom_rate,
                        'secondary_qty': move_dest.secondary_qty
                    })
  
        # elif res.purchase_line_id and res.purchase_line_id.secondary_uom_enabled and res.purchase_line_id.secondary_uom_id:
        #     res.update({
        #         'secondary_uom_id': res.purchase_line_id.secondary_uom_id.id,
        #         'secondary_qty': res.purchase_line_id.secondary_qty
        #     })
        return res

    def _set_quantities_to_reservation(self):
        res = super(StockMove, self)._set_quantities_to_reservation()
        for move in self:
            if move.state not in ('partially_available', 'assigned'):
                continue
            for move_line in move.move_line_ids:
                move_line.secondary_done_qty = move_line.secondary_qty

    @api.model
    def _action_assign(self):
        _logger.info('********stock.move._action_assign*********')
        """
        Reserve stock moves by creating their stock move lines.
        """

        # 临时修改库存
        for move in self.filtered(lambda m: m.state in ['confirmed', 'waiting', 'partially_available']):
            original_quantities = {}
            
            # 获取本公司的is_for_delivery的库存区域
            is_for_delivery_locations = self.env['stock.location'].search([
                ('usage', '=', 'internal'),
                ('is_for_delivery', '=', True),
                ('company_id', '=', move.company_id.id)
            ])
            _logger.info(f'     is_for_delivery_locations: %s', is_for_delivery_locations.mapped('complete_name'))
            
            locations_to_exclude = is_for_delivery_locations
            
            sale_order_id = move.group_id and move.group_id.sale_id
            _logger.info('     sale_order_id: %s', sale_order_id)

            if sale_order_id:
                # 获取当前销售订单的delivery.job.stop
                delivery_job_stop = self.env['delivery.job.stop'].search([('order_id', '=', sale_order_id.id)], limit=1)
                if delivery_job_stop:
                    _logger.info(f'     delivery_job_stop: %s', delivery_job_stop.job_id.name)
                    preparing_locations = delivery_job_stop.job_id.preparing_location_ids
                    _logger.info(f'     正确区域: %s', preparing_locations.mapped('complete_name'))
                    # 需要排除的区域：非当前订单相关的is_for_delivery区域
                    locations_to_exclude = is_for_delivery_locations - preparing_locations
                    
            _logger.info(f'     排除区域: %s', locations_to_exclude.mapped('complete_name'))
            _logger.info(f'     排除区域: %s', locations_to_exclude.mapped('id'))
            _logger.info(f'     商品: %s', move.product_id)
            # 临时将非当前订单相关的is_for_delivery区域的库存设为0
            quants_to_exclude = self.env['stock.quant'].search([
                ('location_id', 'in', locations_to_exclude.ids),
                ('product_id', '=', move.product_id.id),
                ('quantity', '>', 0),
            ])
            _logger.info(quants_to_exclude);
            # 改为调整reserved数量（不能修改quantity）
            for quant in quants_to_exclude:
                original_quantities[quant.id] = quant.reserved_quantity
                quant.write({'reserved_quantity': quant.quantity})

            # 调用super方法
            move_lines = super(StockMove, move)._action_assign()

            # 恢复原库存
            # 为了确保不覆盖已经预留的库存数量，我们需要在恢复原库存时跳过那些已经预留的数量。这可以通过比较预留前后的库存数量来实现。
            for quant_id, original_qty in original_quantities.items():
                quant = self.env['stock.quant'].browse(quant_id)
                quant.write({'reserved_quantity': original_qty})

        return True

class StockQuant(models.Model):
    _inherit = 'stock.quant'

    def reserve_move_line(self, qty):
        """
        Reserve the specified quantity of this quant for a move line.
        """
        move_line = self.env['stock.move.line'].create({
            'product_id': self.product_id.id,
            'product_uom_qty': qty,
            'product_uom_id': self.product_id.uom_id.id,
            'location_id': self.location_id.id,
            'location_dest_id': self.env.ref('stock.stock_location_stock').id,
            'move_id': self.move_id.id,
            'qty_done': qty,
        })
        self.quantity -= qty
        self.reserved_quantity += qty
        
class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    secondary_done_qty = fields.Float("Secondary QTY Done")

    secondary_qty = fields.Float("Secondary QTY", related="move_id.secondary_qty")
    secondary_uom_enabled = fields.Boolean("Secondary UoM Enabled?", related="move_id.secondary_uom_enabled")
    secondary_uom_id = fields.Many2one("uom.uom", 'Secondary UoM', related="move_id.secondary_uom_id")
    secondary_uom_name = fields.Char("Secondary Unit", related="move_id.secondary_uom_name")
    secondary_uom_rate = fields.Float("Secondary Unit Rate", related="move_id.secondary_uom_rate")
    description_with_counts = fields.Char(string='Item Description', compute='_compute_description_with_counts', store=True)

    @api.depends('product_id', 'secondary_uom_enabled', 'secondary_qty')
    def _compute_description_with_counts(self):
        for rec in self:
            if rec.secondary_uom_enabled:
                rec.description_with_counts = "%s (%s %s)" % (rec.product_id.display_name, rec.secondary_qty, rec.secondary_uom_name)
            else:
                rec.description_with_counts = rec.product_id.display_name

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

            _logger.info(move_line.secondary_uom_enabled)
            _logger.info(move_line.secondary_uom_id)
            _logger.info(move_line.secondary_uom_name)
            _logger.info(move_line.secondary_uom_rate)
            _logger.info(move_line.secondary_qty)
            _logger.info('-------------------------------')
            if line_key not in aggregated_move_lines:
                aggregated_move_lines[line_key] = {'name': name,
                                                   'description': description,
                                                   'qty_done': move_line.qty_done,
                                                   'product_uom': uom.name,
                                                   'product': move_line.product_id,
                                                   'secondary_qty':move_line.secondary_qty,
                                                   'secondary_uom':move_line.secondary_uom_name
                                                   }
            else:
                aggregated_move_lines[line_key]['qty_done'] += move_line.qty_done
        return aggregated_move_lines


class StockImmediateTransfer(models.TransientModel):
    _inherit = 'stock.immediate.transfer'

    def process(self):
        res = super(StockImmediateTransfer, self).process()
        for picking_ids in self.pick_ids:
            for moves in picking_ids.move_ids_without_package:
                if moves.secondary_uom_id:
                    moves.secondary_done_qty = moves.secondary_qty
                for move_lines in moves.move_line_ids:
                    if move_lines.secondary_uom_id:
                        move_lines.secondary_qty = move_lines.secondary_done_qty
        return res
