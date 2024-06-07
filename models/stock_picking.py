# -*- coding: UTF-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, models, fields, api
from odoo.exceptions import UserError, ValidationError
import logging
_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = "stock.picking"

    quantity_counts = fields.Char(string='Quantity Counts', compute='_compute_quantity_counts', store=False)

    @api.depends('move_lines')
    def _compute_quantity_counts(self):
        for rec in self:
            results = []
            for line in rec.move_lines:
                if line.product_qty>0:
                    if line.secondary_uom_enabled:
                        fres = list(filter(lambda x: x['uom_name'].lower()==line.secondary_uom_name.lower(), results))
                        if fres:
                            fres[0]['qty'] = fres[0]['qty'] + line.secondary_qty
                        else:
                            results.append({
                                'uom_name': line.secondary_uom_name,
                                'qty': line.secondary_qty
                                })
                    else:
                        fres = list(filter(lambda x: x['uom_name'].lower()==line.product_uom.name.lower(), results))
                        if fres:
                            fres[0]['qty'] = fres[0]['qty'] + line.product_qty
                        else:
                            results.append({
                                'uom_name': line.product_uom.name,
                                'qty': line.product_qty
                                })

            resultString = []
            for line in results:
                if line['qty'] > 1:
                    resultString.append(str(line['qty']) + " " + line['uom_name'] + "s")
                elif line['qty'] > 0:
                    resultString.append(str(line['qty']) + " " + line['uom_name'])
            
            if resultString:
                rec.quantity_counts = 'Quantity Counts: ' + ('; '.join(resultString))
            else:
                rec.quantity_counts = ''

    # def action_assign(self):
    #     res = super(StockPicking, self).action_assign()
    #     if self.picking_type_id.code == 'incoming' and self.company_id.mrp_location_id and self.company_id.ricai_location_id:
    #         self._create_specific_moves()
    #     return res

    # def _create_specific_moves(self):
    #     for move in self.move_lines:
    #         if move.purchase_line_id:
    #             so_total_qty = sum(so.quantity for so in move.purchase_line_id.so_ids)
    #             mo_total_qty = sum(mo.quantity for mo in move.purchase_line_id.mo_ids)

    #             if so_total_qty > 0:
    #                 self._create_internal_move(move, so_total_qty, self.company_id.ricai_location_id)

    #             if mo_total_qty > 0:
    #                 self._create_internal_move(move, mo_total_qty, self.company_id.mrp_location_id)

    # def _create_internal_move(self, original_move, quantity, destination_location):
    #     if destination_location and quantity > 0:
    #         move_vals = {
    #             'name': original_move.name,
    #             'product_id': original_move.product_id.id,
    #             'product_uom_qty': quantity,
    #             'product_uom': original_move.product_uom.id,
    #             'location_id': original_move.location_dest_id.id,
    #             'location_dest_id': destination_location.id,
    #             'picking_id': original_move.picking_id.id,
    #             'state': 'confirmed',
    #         }
    #         self.env['stock.move'].create(move_vals)

    def action_split_picking(self):
        self.ensure_one()
        for move in self.move_lines:
            remaining_qty = move.product_uom_qty
            _logger.info(f('remaining_qty: %s', remaining_qty)
            so_total = 0
            # 只分配足够的数量，避免出现负数
            for so in move.so_ids:
                if remaining_qty>0:
                    line_qty = min(remaining_qty, so.quantity)
                    remaining_qty = remaining_qty - line_qty
                    _logger.info(f('    %s: %s', line_qty, remaining_qty)
                    
                    so_total += line_qty

            mo_total = 0
            for mo in move.mo_ids:
                if remaining_qty>0:
                    line_qty = min(remaining_qty, so.quantity)
                    remaining_qty = remaining_qty - line_qty
                    _logger.info(f('    %s: %s', line_qty, remaining_qty)
                    
                    mo_total += line_qty
                        
            if so_total>0:
                new_move = move.copy({
                    'product_uom_qty': so_total,
                    'location_dest_id': self.company_id.ricai_location_id,
                })
            if mo_total>0:
                new_move = move.copy({
                    'product_uom_qty': mo_total,
                    'location_dest_id': self.company_id.mrp_location_id,
                })
            # 把remaining_qty 更新到原来的move上
            move.write({'product_uom_qty': remaining_qty})

    def button_validate(self):
        if self.picking_type_id.code == 'incoming':
            if not self.company_id.ricai_location_id or not self.company_id.mrp_location_id:
                raise UserError(f"Missing location...")
            self.action_split_picking()
        return super(StockPicking, self).button_validate()