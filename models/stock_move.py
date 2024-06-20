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
        move_lines = super(StockMove, self)._action_assign()

        for move in self:
            _logger.info(move.state)
            if move.state not in ['waiting', 'confirmed']:
                continue

            _logger.info(move)
            sale_order_id = move.group_id and move.group_id.sale_id
            _logger.info('     sale_order_id: %s', sale_order_id)
            
            # 获取公共库存区域
            general_stock_locations = self.env['stock.location'].search([
                ('usage', '=', 'internal'),
                ('is_for_delivery', '=', False)
            ])
            allowed_locations = general_stock_locations

            if sale_order_id:
                # 获取 delivery.job.stop
                delivery_job_stop = self.env['delivery.job.stop'].search([('order_id', '=', sale_order_id.id)], limit=1)
                _logger.info('     delivery_job_stop:')
                _logger.info(delivery_job_stop)
                if delivery_job_stop:
                    # 获取对应的 preparing_location_ids
                    preparing_locations = delivery_job_stop.job_id.preparing_location_ids
                    if preparing_locations:
                        allowed_locations = preparing_locations | general_stock_locations
                        
                _logger.info('     allowed_locations:')
                _logger.info(allowed_locations)
                # 获取满足条件的 quants
                quants = self.env['stock.quant'].search([
                    ('product_id', '=', move.product_id.id),
                    ('location_id', 'in', allowed_locations.ids),
                    ('quantity', '>', 0)
                ])
                reserved_quantity = 0
                _logger.info(quants)
                for quant in quants:
                    if reserved_quantity >= move.product_uom_qty:
                        break
                    remaining_qty = move.product_uom_qty - reserved_quantity
                    to_reserve_qty = min(remaining_qty, quant.quantity)
                    self.env['stock.move.line'].create({
                        'move_id': move.id,
                        'product_id': move.product_id.id,
                        'product_uom_id': move.product_uom.id,
                        'location_id': quant.location_id.id,
                        'location_dest_id': move.location_dest_id.id,
                        'qty_done': to_reserve_qty,
                    })
                    quant.quantity -= to_reserve_qty
                    reserved_quantity += to_reserve_qty

                if reserved_quantity < move.product_uom_qty:
                    raise ValidationError(_('Not enough stock in the specified locations for the order %s.') % sale_order_id.name)
            else:
                # 处理没有关联的情况
                quants = self.env['stock.quant'].search([
                    ('product_id', '=', move.product_id.id),
                    ('location_id', 'in', general_stock_locations.ids),
                    ('quantity', '>', 0)
                ])
                reserved_quantity = 0
                for quant in quants:
                    if reserved_quantity >= move.product_uom_qty:
                        break
                    remaining_qty = move.product_uom_qty - reserved_quantity
                    to_reserve_qty = min(remaining_qty, quant.quantity)
                    self.env['stock.move.line'].create({
                        'move_id': move.id,
                        'product_id': move.product_id.id,
                        'product_uom_id': move.product_uom.id,
                        'location_id': quant.location_id.id,
                        'location_dest_id': move.location_dest_id.id,
                        'qty_done': to_reserve_qty,
                    })
                    quant.quantity -= to_reserve_qty
                    reserved_quantity += to_reserve_qty

                if reserved_quantity < move.product_uom_qty:
                    raise ValidationError(_('Not enough stock in the general stock locations for the move %s.') % move.name)

        return move_lines

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
